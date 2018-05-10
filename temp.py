@app.route('/service/login/', methods=['GET', 'POST'])
@notloggedin_required
@csrf.exempt
def login():
    try:
        loginform = LoginForm()

        # Check for preferred language
        user_language = get_locale()

        # Check which traveler user was watching
        which_traveler = ft_functions.get_traveler()

        # Login data have been submitted (POST)
        if request.method == 'POST':
            print('Login() POST')
            if loginform.validate_on_submit():
                print('Login form validates')
                email = loginform.email.data
                password = loginform.password.data

                client = MongoClient()
                db = client.TeddyGo
                users = db.users

                # Check if email exist in DB and is verified, exit if not
                docID = None
                if users.find_one({'email': email}):
                    docID = users.find_one({'email': email}).get('_id')
                    status = users.find_one({'_id': docID}).get('email_verified')
                    if not status:
                        flash(
                            lazy_gettext('Such email is registered but hasn\'t been verified yet. '
                            'If it\'s your email please verify it, otherwise choose different credentials to log in or <a href="/register/">register</a>'),
                            'header')
                        #return render_template('login.html', loginform=loginform, subscribe2updatesform=subscribe2updatesform, language=user_language)
                        return redirect(url_for('login'))
                else:
                    flash(
                        lazy_gettext('Sorry, we do not recognize this email address. Please choose different credentials or <a href="/register/">register</a>'),
                        'header')
                    #return render_template('login.html', loginform=loginform, subscribe2updatesform=subscribe2updatesform, language=user_language)
                    return redirect(url_for('login'))

                # If Ok, check for a password
                pwd_should_be = users.find_one({'_id': docID})['password']
                if sha256_crypt.verify(password, pwd_should_be):
                    flash(lazy_gettext('Login successfull!'), 'header')

                    # Update session data
                    session['LoggedIn'] = 'yes'
                    session['Email'] = email

                    if which_traveler == 'All':
                        next_redirect = '/'
                    else:
                        next_redirect = '/{}/'.format(which_traveler)

                    # Update coockies
                    logged_in = request.cookies.get('LoggedIn', None)
                    if not logged_in:
                        expire_date = datetime.datetime.now()
                        expire_date = expire_date + datetime.timedelta(days=30)
                        redirect_to_index = redirect(next_redirect)
                        response = app.make_response(redirect_to_index)
                        response.set_cookie('LoggedIn', 'yes', expires=expire_date)
                        response.set_cookie('Email', email, expires=expire_date)
                        print('LoggedIn and Email cookies set')
                        return response
                    else:
                        print('LoggedIn and Email cookies already exist')
                        return redirect(next_redirect)

                # Invalid password
                else:
                    flash(lazy_gettext('Wrong password'), 'header')
                    #return render_template('login.html', loginform=loginform, subscribe2updatesform=subscribe2updatesform, language=user_language)
                    return redirect(url_for('login'))

            # Login form did not validate on submit
            else:
                return render_template('login.html', loginform=loginform)
        # GET request
        else:
            return render_template('login.html', loginform=loginform)

    except Exception as e:
        print('register() exception: {}'.format(e))
        if which_traveler == 'All':
            return redirect(url_for('index'))
        else:
            return redirect(url_for('traveler'))