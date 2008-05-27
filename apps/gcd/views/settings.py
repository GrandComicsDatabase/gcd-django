from django.shortcuts import render_to_response
from django.http import HttpResponse

def settings(request):
    if request.method == 'POST':
        if len(request.session.keys()) > 0: 
            #we might have set the test_cookie
            if request.session.test_cookie_worked():
                request.session.delete_test_cookie()
            if (request.POST["entries"] != ""):
                if request.POST['entries'].isdigit():
                    request.session['entries_per_page'] = \
                      int(request.POST['entries'])
            return HttpResponse("Settings saved.")
        else:
            return HttpResponse("Please enable cookies and try again.")

    if len(request.session.keys()) == 0:
        request.session.set_test_cookie()
    return render_to_response('settings.html')