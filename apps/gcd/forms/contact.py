from django.conf import settings
from contact_form.forms import ContactForm

class CustomContactForm(ContactForm):
    recipient_list = ['%s' % settings.DEFAULT_FROM_EMAIL,]
    from_email = 'do-not_reply@comics.org'
