import os


def customization(request):
    version = os.environ.get('VERSION_NUMBER', '0.x')
    update_date = os.environ.get('UPDATE_DATE', '')
    static_version = version if version != 'dev' else update_date.replace('-', '.')
    customizable = {
        'organization': os.environ.get('ORGANIZATION', '4TV'),
        'contact_email': os.environ.get('CONTACT_EMAIL', 'askcos_support@mit.edu'),
        'support_emails': os.environ.get('SUPPORT_EMAILS', 'askcos_support@mit.edu'),
        'email_enabled': bool(os.environ.get('EMAIL_ENABLED', False)),
        'version_number': version,
        'update_date': update_date,
        'static_version': static_version,
    }
    return customizable
