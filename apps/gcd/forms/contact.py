from django.conf import settings
from django_contact_form.forms import ContactForm
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV3

class CustomContactForm(ContactForm):
    recipient_list = ['%s' % settings.DEFAULT_FROM_EMAIL,]
    from_email = settings.DEFAULT_FROM_EMAIL
    captcha = ReCaptchaField(widget=ReCaptchaV3(action='contact_form'))
