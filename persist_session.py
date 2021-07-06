import pickle
import datetime
import os
from urllib.parse import urlparse
import requests
import getpass
from threading import Timer

class RefreshTimer(Timer):

    def run(self):
        while not self.finished.wait(self.interval):
            self.function(*self.args, **self.kwargs)


        
class PersistLoginSession:
    """
    a class which handles and saves login sessions. It also keeps track of proxy settings.
    It does also maintine a cache-file for restoring session data from earlier
    script executions.
    """
    def __init__(self,
                 loginUrl,
                 loginEmail,
                 CheckInUrl,
                 sessionFileAppendix = '_session.dat',
                 maxSessionTimeSeconds = 12 * 60 * 60,
                 proxies = None,
                 userAgent = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.1',
                 debug = True,
                 forceLogin = False,
                 **kwargs):
        """
        save some information needed to login the session

        'proxies' is of format { 'https' : 'https://user:pass@server:port', 'http' : ...
        'loginData' will be sent as post data (dictionary of id : value).
        'maxSessionTimeSeconds' will be used to determine when to re-login.
        """
        urlData = urlparse(loginUrl)

        self.proxies = proxies
        self.loginEmail = loginEmail
        self.loginUrl = loginUrl
        self.CheckInUrl = CheckInUrl
        self.maxSessionTime = maxSessionTimeSeconds
        self.sessionFile = urlData.netloc + sessionFileAppendix

        self.userAgent = userAgent
        self.debug = debug

        self.isLoggedIn = False

        self.login(forceLogin, **kwargs)

        if self.isLoggedIn:
            self.autoRefresh = RefreshTimer(4*60*60, self.refresh)

    def __del__(self):
        # body of destructor
        if self.authRefresh:
            self.autoRefresh.cancel()

    def modification_date(self, filename):
        """
        return last file modification date as datetime object
        """
        t = os.path.getmtime(filename)
        return datetime.datetime.fromtimestamp(t)

    def login(self, forceLogin = False, **kwargs):
        """
        login to a session. Try to read last saved session from cache file. If this fails
        do proper login. If the last cache access was too old, also perform a proper login.
        Always updates session cache file.
        """
        wasReadFromCache = False
        if self.debug:
            print('loading or generating session...')
        if os.path.exists(self.sessionFile) and not forceLogin:
            time = self.modification_date(self.sessionFile)         

            # only load if file less than 12 hours old
            lastModification = (datetime.datetime.now() - time).seconds
            if lastModification < self.maxSessionTime:
                with open(self.sessionFile, "rb") as f:
                    self.session = pickle.load(f)
                    if self.debug:
                        print("loaded session from cache (last access %ds ago) "
                              % lastModification)
                        wasReadFromCache = self.refresh()

        if not wasReadFromCache:
            password = getpass.getpass("Password for " + self.loginEmail + ": ")
            self.session = requests.Session()
            self.session.headers.update({'user-agent' : self.userAgent, 'Content-Type': 'application/json'})
            res = self.session.post(
              self.loginUrl, 
              json = {"email": self.loginEmail, "password": password}, 
              proxies = self.proxies, 
              **kwargs
            )
            self.saveSessionToCache()
            if res.json()['ok']:
              self.isLoggedIn = True

            if self.debug:
                if res.json()['ok']:
                    print('created new session with login' )
                else:
                    print('login has failed')


    def refresh(self):
        """
        refresh a session. Send check-in request to update the session. Return if session is valid or not
        """
        res = self.session.post(self.CheckInUrl)
        print (res)
        if not res.json()['ok']:
            if self.debug:
                print("refreshing session failed")
            self.isLoggedIn = False
            return False
        else:
            if self.debug:
                print("session refreshed")
            self.saveSessionToCache()
            self.isLoggedIn = True
            return True



    def saveSessionToCache(self):
        """
        save session to a cache file
        """
        # always save (to update timeout)
        with open(self.sessionFile, "wb") as f:
            pickle.dump(self.session, f)
            if self.debug:
                print('updated session cache-file %s' % self.sessionFile)

    def retrieveContent(self, url, method = "get", postData = None, **kwargs):
        """
        return the content of the url with respect to the session.

        If 'method' is not 'get', the url will be called with 'postData'
        as a post request.
        """
        if method == 'post':
            res = self.session.post(url , data = postData, proxies = self.proxies, **kwargs)
        elif method == 'delete':
            res = self.session.delete(url , proxies = self.proxies, **kwargs)
        else:
            res = self.session.get(url , proxies = self.proxies, **kwargs)

        return res

    def get(self, url, **kwargs):
        """
        return the content of the url with respect to the session, using 'get'
        """
        return self.session.get(url , proxies = self.proxies, **kwargs)

    def post(self, url, postData = None, json = None, **kwargs):
        """
        return the content of the url with respect to the session, using 'get'
        """
        return self.session.get(url, data = postData, json = json, proxies = self.proxies, **kwargs)

    def delete(self, url, **kwargs):
        """
        return the content of the url with respect to the session, using 'get'
        """
        return self.session.delete(url , proxies = self.proxies, **kwargs)

