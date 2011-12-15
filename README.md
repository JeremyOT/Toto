SimpleAPIServer
===============
SimpleAPIServer is a small framework intended to accelerate API server development. It is
built on top of [Tornado][tornado] and can currently use either [MySQL][mysql] or [MongoDB][mongodb] as a
backing database.

Features
--------
* Uses JSON for easy consumption by clients on any platform
* Easy to add new methods
* Simple authentication built in with HMAC verification for authenticated requests
* Session state persistence for authenticated requests
* Sessions stored in database to simplify scaling across servers

Configuration
-------------
SimpleAPIServer is comes configured to run on port 8888 and connect to a MongoDB server
running on localhost. Configuration can be through server.conf or command line parameters
(--option='string value' --option=1234) or a combination thereof - useful when launching
multiple instances on different ports. Run `python server.py --help` for a full list of
available parameters.

Customization
-------------
Methods are referenced by name in each request. `a.b.c` maps to `a/b/c.py`. To add new
methods, add modules and packages to the simpleapi package (see the account package for
reference) and ensure that each callable module defines `invoke(handler, parameters)`
where `handler` is the SimpleAPIHandler (subclass of tornado.web.RequestHandler) handling
the current request.

`handler.connection.db` provides direct access to the database used by the sessions and
accounts framework.

`handler.session` provides access to the current session or `None` if not authenticated.
Available properties:
* `session.user\_id` - the current user ID
* `session.expires` - the unix timestamp when the session will expire
* `session.session_id` - the current session ID
* `session.state` - a python dict containing the current state, you must call
`session.save_state()` to persist any changes


[tornado]:www.tornadoweb.org
[mysql]:http://www.mysql.com
[mongodb]:http://www.mongodb.org
