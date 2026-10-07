def _mail_recipient(
        recipient_name: str, recipient_email: str, sender_name: str,
        sender_url: str, subject: Any, body: Any,
        body_html: Optional[Any] = None,
        headers: Optional[dict[str, Any]] = None,
        attachments: Optional[Iterable[Attachment]] = None) -> None:

    if not headers:
        headers = {}

    if not attachments:
        attachments = []

    mail_from = config.get('smtp.mail_from')

    reply_to = config.get('smtp.reply_to')

    msg = EmailMessage()

    msg.set_content(body, cte='base64')

    if body_html:
        msg.add_alternative(body_html, subtype='html', cte='base64')

    for k, v in headers.items():
        if k in msg.keys():
            msg.replace_header(k, v)
        else:
            msg.add_header(k, v)
    msg['Subject'] = subject
    msg['From'] = utils.formataddr((sender_name, mail_from))
    msg['To'] = utils.formataddr((recipient_name, recipient_email))
    msg['Date'] = utils.formatdate(time())
    if not config.get('ckan.hide_version'):
        msg['X-Mailer'] = "CKAN %s" % ckan.__version__
    # Check if extension is setting reply-to via headers or use config option
    if reply_to and reply_to != '' and not msg['Reply-to']:
        msg['Reply-to'] = reply_to

    for attachment in attachments:
        if len(attachment) == 3:
            name, _file, media_type = attachment
        else:
            name, _file = attachment
            media_type = None

        if not media_type:
            media_type, _encoding = mimetypes.guess_type(name)
        if media_type:
            main_type, sub_type = media_type.split('/')
        else:
            main_type = sub_type = None

        msg.add_attachment(
            _file.read(), filename=name, maintype=main_type, subtype=sub_type)

    # Send the email using Python's smtplib.
    smtp_server = config.get('smtp.server')
    smtp_starttls = config.get('smtp.starttls')
    smtp_starttls_verify = config.get('smtp.starttls_verify')
    smtp_starttls_ca_bundle = config.get('smtp.starttls_ca_bundle')
    if smtp_starttls_ca_bundle and not os.path.exists(smtp_starttls_ca_bundle):
        raise MailerException(
            "SMTP CA bundle path (smtp.starttls_ca_bundle) "
            f"does not exist: {smtp_starttls_ca_bundle}"
        )
    smtp_user = config.get('smtp.user')
    smtp_password = config.get('smtp.password')

    host, port = _parse_smtp_server(smtp_server)
    if not host:
        raise MailerException('SMTP server hostname is not configured')

    try:
        smtp_connection = smtplib.SMTP(host, port)
    except (socket.error, smtplib.SMTPConnectError) as e:
        log.exception(e)
        raise MailerException('SMTP server could not be connected to: "%s" %s'
                              % (smtp_server, e))

    try:
        # Identify ourselves and prompt the server for supported features.
        smtp_connection.ehlo()

        # If 'smtp.starttls' is on in CKAN config, try to put the SMTP
        # connection into TLS mode.
        if smtp_starttls:
            if smtp_connection.has_extn('STARTTLS'):
                if smtp_starttls_verify:
                    if smtp_starttls_ca_bundle:
                        if os.path.isfile(smtp_starttls_ca_bundle):
                            context = ssl.create_default_context(
                                cafile=smtp_starttls_ca_bundle
                            )
                        elif os.path.isdir(smtp_starttls_ca_bundle):
                            context = ssl.create_default_context(
                                capath=smtp_starttls_ca_bundle
                            )
                        else:
                            raise MailerException(
                                "SMTP CA bundle path (smtp.starttls_ca_bundle) "
                                f"can not be accessed: {smtp_starttls_ca_bundle}"
                            )
                    else:
                        context = ssl.create_default_context()
                    smtp_connection.starttls(context=context)
                else:
                    smtp_connection.starttls()
                # Re-identify ourselves over TLS connection.
                smtp_connection.ehlo()
            else:
                raise MailerException("SMTP server does not support STARTTLS")

        # If 'smtp.user' is in CKAN config, try to login to SMTP server.
        if smtp_user:
            assert smtp_password, ("If smtp.user is configured then "
                                   "smtp.password must be configured as well.")
            smtp_connection.login(smtp_user, smtp_password)

        smtp_connection.sendmail(mail_from, [recipient_email], msg.as_string())
        log.info("Sent email to %s", recipient_email)

    except smtplib.SMTPException as e:
        msg = '%r' % e
        log.exception(msg)
        raise MailerException(msg)
    finally:
        smtp_connection.quit()
