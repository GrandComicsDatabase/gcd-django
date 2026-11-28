"""The reader of rendered forms that the bulk change tests use."""
from apps.oi.tests.bulk.page_forms import PageForms

PAGE = """
<input name="outside" value="no">
<form method="post" action="/go/">
  <input type="hidden" name="token" value="a&amp;b">
  <input type="checkbox" name="flag" checked>
  <input type="checkbox" name="other">
  <input type="radio" name="pick" value="1">
  <input type="radio" name="pick" value="2" checked>
  <input type="submit" name="save" value="Save">
  <input type="file" name="scan">
  <input name="off" value="x" disabled>
  <select name="one"><option value="a">A</option><option value="b">B</option>
  </select>
  <select name="many" multiple><option value="c" selected>C</option>
    <option value="d" selected>D</option><option value="e">E</option>
  </select>
  <select name="box" size="3"><option value="f">F</option></select>
  <textarea name="notes">
Two
lines</textarea>
</form>
<a href="/list/?x=1&amp;_export=bulk">bulk</a>
<p id="same"></p><p id="same"></p>
"""


def test_forms_as_a_browser_submits_them():
    """Each kind of field gives the data that a browser sends."""
    page = PageForms(PAGE)
    form = page.form('POST', '/go/')

    assert page.data(form) == {
      'token': ['a&b'], 'flag': ['on'], 'pick': ['2'], 'one': ['a'],
      'many': ['c', 'd'], 'notes': ['Two\nlines']}
    assert page.data(form, pick='1')['pick'] == ['1']
    assert page.link('_export=bulk') == '/list/?x=1&_export=bulk'
    assert page.repeated_ids() == ['same']
