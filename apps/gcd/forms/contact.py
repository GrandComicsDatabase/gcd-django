from django.conf import settings
from django_contact_form.forms import ContactForm
from captcha.fields import ReCaptchaField

class CustomContactForm(ContactForm):
    recipient_list = ['%s' % settings.DEFAULT_FROM_EMAIL,]
    from_email = settings.DEFAULT_FROM_EMAIL
    captcha = ReCaptchaField()
