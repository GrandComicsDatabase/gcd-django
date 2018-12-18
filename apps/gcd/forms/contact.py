from django.conf import settings
from contact_form.forms import ContactForm
from captcha.fields import ReCaptchaField

class CustomContactForm(ContactForm):
    recipient_list = ['%s' % settings.DEFAULT_FROM_EMAIL,
                      'gcd-contact@googlegroups.com']
    from_email = 'do-not_reply@comics.org'
    captcha = ReCaptchaField()