"""Cold-import coverage for Django's concurrent development-server startup."""

from pathlib import Path
import subprocess
import sys
import textwrap


def test_markdown_extension_waits_for_concurrent_package_initialization():
    # pytest/Django may already have imported Markdown. Use a fresh interpreter
    # and coordinate real imports instead of relying on a stress loop.
    script = textwrap.dedent('''
        import builtins
        import threading
        import traceback

        parent_ready = threading.Event()
        release_parent = threading.Event()
        failures = []
        original_import = builtins.__import__

        def controlled_import(name, globals=None, locals=None,
                              fromlist=(), level=0):
            caller = (globals or {}).get('__name__')
            owner = threading.current_thread().name
            if (owner == 'markdown-parent' and caller == 'markdown'
                    and name == 'core' and level == 1):
                # Keep the parent package initializing while GCD starts its
                # import, as happens during URLconf/template-library startup.
                parent_ready.set()
                if not release_parent.wait(5):
                    raise AssertionError('GCD did not reach its import gate')
            elif owner == 'gcd-extension':
                parent_import = (
                    caller == 'apps.gcd.markdown_extension'
                    and name == 'markdown' and level == 0
                )
                child_import = (
                    caller == 'markdown.treeprocessors'
                    and name == '' and level == 1
                )
                if parent_import or child_import:
                    # A top-level import waits for the package safely. The
                    # old submodule-first path instead holds treeprocessors'
                    # import lock while it waits for that same package.
                    release_parent.set()
            return original_import(name, globals, locals, fromlist, level)

        builtins.__import__ = controlled_import

        def import_parent():
            try:
                import markdown
                assert markdown.markdown('**ready**') == (
                    '<p><strong>ready</strong></p>'
                )
            except BaseException:
                failures.append(traceback.format_exc())

        def import_extension():
            try:
                from apps.gcd import markdown_extension
                assert issubclass(markdown_extension.TailwindTreeProcessor,
                                  markdown_extension.Treeprocessor)
            except BaseException:
                failures.append(traceback.format_exc())

        parent = threading.Thread(target=import_parent,
                                  name='markdown-parent', daemon=True)
        extension = threading.Thread(target=import_extension,
                                     name='gcd-extension', daemon=True)
        parent.start()
        assert parent_ready.wait(5), 'Markdown did not reach the import gate'
        extension.start()
        parent.join(8)
        extension.join(8)
        assert not parent.is_alive(), 'Markdown import deadlocked'
        assert not extension.is_alive(), 'GCD extension import deadlocked'
        assert not failures, '\\n'.join(failures)
    ''')
    result = subprocess.run(
        [sys.executable, '-B', '-c', script],
        cwd=Path(__file__).resolve().parents[3],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
