def send_reset_link(user: model.User) -> None:
    create_reset_key(user)
    body = get_reset_link_body(user)
    extra_vars = {
        'site_title': config.get('ckan.site_title')
    }
    subject = render('emails/reset_password_subject.txt', extra_vars)

    # Make sure we only use the first line
    subject = subject.split('\n')[0]

    mail_user(user, subject, body)
