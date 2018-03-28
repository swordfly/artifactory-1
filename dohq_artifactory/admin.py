import logging
import random
import time

from dohq_artifactory.exception import ArtifactoryException


def rest_delay():
    time.sleep(0.5)


def gen_passwd(pw_len=16):
    alphabet_lower = 'abcdefghijklmnopqrstuvwxyz'
    alphabet_upper = alphabet_lower.upper()
    alphabet_len = len(alphabet_lower)
    pwlist = []

    for i in range(pw_len // 3):
        r_0 = random.randrange(alphabet_len)
        r_1 = random.randrange(alphabet_len)
        r_2 = random.randrange(10)

        pwlist.append(alphabet_lower[r_0])
        pwlist.append(alphabet_upper[r_1])
        pwlist.append(str(r_2))

    for i in range(pw_len - len(pwlist)):
        r_0 = random.randrange(alphabet_len)

        pwlist.append(alphabet_lower[r_0])

    random.shuffle(pwlist)

    result = ''.join(pwlist)

    return result


class ArtifactoryObject(object):
    _uri = None

    def __init__(self, artifactory):
        self.additional_params = {}
        self.raw = None

        self._artifactory = artifactory
        self._auth = self._artifactory.auth
        self._session = self._artifactory.session

    def _create_json(self):
        raise NotImplementedError()

    def create(self):
        logging.debug('Create (or update) {x.__class__.__name__} [{x.name}]'.format(x=self))
        data_json = self._create_json()
        data_json.update(self.additional_params)
        request_url = self._artifactory.drive + '/api/{uri}/{x.name}'.format(uri=self._uri, x=self)
        r = self._session.put(
            request_url,
            json=data_json,
            headers={'Content-Type': 'application/json'},
            verify=False,
            auth=self._auth,
        )
        r.raise_for_status()
        rest_delay()
        self._read()

    def _read(self):
        raise NotImplementedError()

    def delete(self):
        logging.debug('Remove {x.__class__.__name__} [{x.name}]'.format(x=self))
        request_url = self._artifactory.drive + '/api/{uri}/{x.name}'.format(uri=self._uri, x=self)
        r = self._session.delete(
            request_url,
            verify=False,
            auth=self._auth,
        )
        r.raise_for_status()
        rest_delay()


class User(ArtifactoryObject):
    _uri = 'security/users'

    def __init__(self, artifactory, name, email, password):
        super(User, self).__init__(artifactory)

        self.name = name
        self.email = email

        self.password = password
        self.admin = False
        self.profileUpdatable = True
        self.internalPasswordDisabled = False
        self.groups = []

        self._lastLoggedIn = None
        self._realm = None

    def _create_json(self):
        data_json = {
            'name': self.name,
            'email': self.email,
            'password': self.password,
            'admin': self.admin,
            "profileUpdatable": self.profileUpdatable,
            "internalPasswordDisabled": self.internalPasswordDisabled,
            "groups": self.groups,
        }
        return data_json

    def _read(self):
        result = True
        request_url = self._artifactory.drive + '/api/security/users/{x.name}'.format(x=self)

        logging.debug('user _read [{x.name}]'.format(x=self))

        r = self._session.get(
            request_url,
            verify=False,
            auth=self._auth,
        )

        if 404 == r.status_code:

            result = False

        else:

            r.raise_for_status()

            # def _read_response(self, response):
            response = r.json()
            self.raw = response

            # self.password = ''  # never returned
            self.name = response['name']
            self.email = response['email']
            self.admin = response['admin']
            self.profileUpdatable = response['profileUpdatable']
            self.internalPasswordDisabled = response['internalPasswordDisabled']
            self.groups = response['groups'] if 'groups' in response else []
            self._lastLoggedIn = response['lastLoggedIn'] if 'lastLoggedIn' in response else '[]'
            self._realm = response['realm'] if 'realm' in response else '[]'

        return result

    def update(self):
        self.create()

    @property
    def encryptedPassword(self):
        if self.password is None:
            raise ArtifactoryException('Please, set [self.password] before query encryptedPassword')

        logging.debug('user get encrypted password [{x.name}]'.format(x=self))

        request_url = self._artifactory.drive + '/api/security/encryptedPassword'

        r = self._session.get(
            request_url,
            verify=False,
            auth=(self.name, self.password),
        )

        r.raise_for_status()
        encryptedPassword = r.text
        return encryptedPassword

    @property
    def lastLoggedIn(self):
        return self._lastLoggedIn

    @property
    def realm(self):
        return self._realm


class Group(ArtifactoryObject):
    _uri = 'security/groups'

    def __init__(self, artifactory, name):
        super(Group, self).__init__(artifactory)

        self.name = name
        self.description = ''
        self.autoJoin = False
        self.realm = ''
        self.realmAttributes = ''

    def _create_json(self):
        data_json = {
            "name": self.name,
            "description": self.description,
            "autoJoin": self.autoJoin,
        }
        return data_json

    def _read(self):

        result = True
        request_url = self._artifactory.drive + '/api/security/groups/{x.name}'.format(x=self)

        logging.debug('user group _read [{x.name}]'.format(x=self))

        r = self._session.get(
            request_url,
            # headers={'Content-Type': 'application/json'},
            verify=False,
            auth=self._auth,
        )

        if 404 == r.status_code:

            result = False

        else:

            r.raise_for_status()

            response = r.json()
            self.raw = response

            self.name = response['name']
            self.description = response['description']
            self.autoJoin = response['autoJoin']
            self.realm = response['realm']
            self.realmAttributes = response.get('realmAttributes', None)

        return result

    def update(self):
        self.create()


class Repository(ArtifactoryObject):
    # List packageType from wiki:
    # https://www.jfrog.com/confluence/display/RTF/Repository+Configuration+JSON#RepositoryConfigurationJSON-application/vnd.org.jfrog.artifactory.repositories.LocalRepositoryConfiguration+json
    MAVEN = "maven"
    GRADLE = "gradle"
    IVY = "ivy"
    SBT = "sbt"
    NUGET = "nuget"
    GEMS = "gems"
    NPM = "npm"
    BOWER = "bower"
    DEBIAN = "debian"
    COMPOSER = "comoser"
    PYPI = "pypi"
    DOCKER = "docker"
    VAGRANT = "vagrant"
    GITLFS = "gitlfs"
    YUM = "yum"
    CONAN = "conan"
    CHEF = "chef"
    PUPPET = "puppet"
    GENERIC = "generic"


class RepositoryLocal(Repository):
    _uri = 'repositories'

    def __init__(self, artifactory, name, packageType=Repository.GENERIC):
        super(RepositoryLocal, self).__init__(artifactory)
        self.name = name
        self.description = ''
        self.packageType = packageType
        self.repoLayoutRef = 'maven-2-default'
        self.archiveBrowsingEnabled = True

    def _create_json(self):
        # Original JSON, add more property if you need
        # https://www.jfrog.com/confluence/display/RTF/Repository+Configuration+JSON
        data_json = {
            "rclass": "local",
            "key": self.name,
            "description": self.description,
            "packageType": self.packageType,
            "notes": "",
            "includesPattern": "**/*",
            "excludesPattern": "",
            "repoLayoutRef": self.repoLayoutRef,
            "dockerApiVersion": "V1",
            "checksumPolicyType": "client-checksums",
            "handleReleases": True,
            "handleSnapshots": True,
            "maxUniqueSnapshots": 0,
            "snapshotVersionBehavior": "unique",
            "suppressPomConsistencyChecks": True,
            "blackedOut": False,
            "propertySets": [],
            "archiveBrowsingEnabled": self.archiveBrowsingEnabled,
            "yumRootDepth": 0,
        }
        return data_json

    def _read(self):

        request_url = self._artifactory.drive + '/api/repositories/{x.name}'.format(x=self)

        logging.debug('repositories read [{x.name}]'.format(x=self))

        r = self._session.get(
            request_url,
            headers={'Content-Type': 'application/json'},
            verify=False,
            auth=self._auth,
        )

        if 404 == r.status_code or 400 == r.status_code:

            result = False

        else:

            result = True

            r.raise_for_status()

            response = r.json()
            self.raw = response

            self.name = response['key']
            self.description = response['description']
            self.layoutName = response['repoLayoutRef']
            self.archiveBrowsingEnabled = response['archiveBrowsingEnabled']

        return result


class PermissionTarget(ArtifactoryObject):
    _uri = 'security/permissions'

    def __init__(self, artifactory, name):
        super(PermissionTarget, self).__init__(artifactory)
        self.name = name
        self.includesPattern = '**'
        self.excludesPattern = ''
        self.repositories = []
        self.principals = {
            'users': {},
            'groups': {},
        }

    def _create_json(self):
        data_json = {
            "name": self.name,
            "includesPattern": self.includesPattern,
            "excludesPattern": self.excludesPattern,
            "repositories": self.repositories,
            "principals": self.principals
        }
        return data_json

    def _read(self):

        result = True
        request_url = self._artifactory.drive + '/api/security/permissions/{x.name}'.format(x=self)

        logging.debug('user _read [{x.name}]'.format(x=self))

        r = self._session.get(
            request_url,
            headers={'Content-Type': 'application/json'},
            verify=False,
            auth=self._auth,
        )

        if 404 == r.status_code:

            result = False

        else:

            r.raise_for_status()

            response = r.json()

            self.name = response['name']
            self.includesPattern = response['includesPattern']
            self.excludesPattern = response['excludesPattern']

            if 'repositories' in response:
                self.repositories = response['repositories']

            if 'principals' in response:

                if 'users' in response['principals']:
                    self.principals['users'] = response['principals']['users']

                if 'groups' in response['principals']:
                    self.principals['groups'] = response['principals']['groups']

        return result
