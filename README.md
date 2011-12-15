SimpleAPIServer
===============
SimpleAPIServer is a small framework intended to accelerate API server development. It is
built on top of [Tornado][tornado] and can currently use either [MySQL][mysql] or [MongoDB][mongodb] as a
backing database.

Features
--------
* Uses JSON for easy consumption by clients on any platform
* Easy to add new methods
* Simple authentication built in with HMAC-SHA1 verification for authenticated requests
* Session state persistence for authenticated requests
* Sessions stored in database to simplify scaling across servers

Configuration
-------------
SimpleAPIServer is comes configured to run on port 8888 and connect to a MongoDB server
running on localhost. Configuration can be through server.conf or command line parameters
(`--option='string value' --option=1234`) or a combination thereof - useful when launching
multiple instances on different ports. Run `python server.py --help` for a full list of
available parameters.

Customization
-------------
Methods are referenced by name in each request. `a.b.c` maps to `a/b/c.py`. To add new
methods, add modules and packages to the simpleapi package (see the account package for
reference) and ensure that each callable module defines `invoke(handler, parameters)`
where `handler` is the `SimpleAPIHandler` (subclass of `tornado.web.RequestHandler`) handling
the current request.

`handler.connection.db` provides direct access to the database used by the sessions and
accounts framework.

`handler.session` provides access to the current session or `None` if not authenticated.
Available properties:

* `session.user_id` - the current user ID
* `session.expires` - the unix timestamp when the session will expire
* `session.session_id` - the current session ID
* `session.state` - a python dict containing the current state, you must call
`session.save_state()` to persist any changes

Method modules can take advantage of [Tornado's][tornado] non-blocking features by setting
the optional module attribute `asynchronous = True`. When the asynchronous operation is
complete you must call `handler.finish()` in order to finish the request. Data can be sent
to the client with `handler.write()` and `handler.flush()`. Optionally, modules can
implement `on_connection_close()` to clean up any resources if the client closes the
connection. See `RequestHandler.on_connection_close()` in the [Tornado][tornado] documentation
for more information.

It is important to remember that [Tornado][tornado] requires that all calls to `write()`,
`flush()` and `finish()` are performed on the main thread. You can schedule a function to
run on the main thread with `IOLoop.instance().add_callback(callback)`.

_Note: Any data returned from a call to `method.invoke()` will be sent to the client as
JSON data and be used to generate the x-hmac header for verification. This may cause
issues with asynchronous methods. If `method.invoke()` returns `None`, a response will not
automatically be sent to the client and no x-hmac header will be generated._

Requests
-----------
Non-authenticated methods:

1. Call service with JSON object in the form: `{"method": "a.b.c", "parameters": <parameters>}`.
2. Parse response JSON.

Account Creation:

1. Call `account.create` method with `{"user_id": <user_id>, "password": <password>}`.
2. Verify that the HMAC of the response body with `<user_id>` as the key matches the `x-hmac` 
header in the response.
3. Parse response JSON.
4. Read and store `session_id` from the response object.

Login:

1. Call `account.login` method with `{"user_id": <user_id>, "password": <password>}`.
2. Verify that the HMAC of the response body with `<user_id>` as the key matches the `x-hmac`
header in the response.
3. Parse response JSON.
4. Read and store `session_id` from the response object.

Authenticated methods:

1. Login (see-above).
2. Call service with JSON object in the form: `{"method": "a.b.c", "parameters": <parameters>}`
with the `x-session-id` header set to the session ID returned from login and the `x-hmac` header
set to the SHA1 HMAC generated with `<user_id>` as the key and the JSON request string as
the message.
3. Verify that the HMAC of the response body with `<user_id>` as the key matches the `x-hmac`
header in the response.
4. Parse response JSON.

_Note: These instructions assume that `method.invoke()` returns an object to be serialized
and sent to the client. Methods that return None can be used the send any data and must be
handled accordingly._

[tornado]:http://www.tornadoweb.org
[mysql]:http://www.mysql.com
[mongodb]:http://www.mongodb.org
