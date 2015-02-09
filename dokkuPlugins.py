#!/usr/bin/env python

import argparse
import httplib2
import re
import sys

from bs4 import BeautifulSoup, SoupStrainer
from os import environ
from github import GitHub, ApiNotFoundError
from tabulate import tabulate

# TODO: modularize __init__
# TODO: use gh module to get owner information
# TODO: use gh to find real url so we don't have to retry???


class dokkuPlugins(object):

    def __init__(self):
        self.pluginTypes = ['backup-check', 'backup-export', 'backup-import', 'bind-external-ip', 'check-deploy', 'commands', 'dependencies',
                            'docker-args', 'docker-args-build', 'docker-args-deploy', 'docker-args-run', 'git-post-pull', 'git-pre-pull',
                            'install', 'nginx-hostname', 'nginx-pre-reload', 'post-build', 'post-build-buildstep', 'post-build-dockerfile',
                            'post-delete', 'post-deploy', 'post-domains-update', 'post-release', 'post-release-buildstep', 'post-release-dockerfile',
                            'pre-build', 'pre-build-buildstep', 'pre-build-dockerfile', 'pre-delete', 'pre-deploy', 'pre-release', 'pre-release-buildstep',
                            'pre-release-dockerfile', 'receive-app', 'update']
        self.plugins = []
        http = httplib2.Http()
        _, response = http.request('http://progrium.viewdocs.io/dokku/plugins')
        print 'Retrieving dokku plugin metadata...\n'

        # response = """<a href="https://github.com/F4-Group/dokku-apt">APT</a> \
        # <a href="https://github.com/blag/dokku-elasticsearch-plugin">dokku-elasticsearch-plugin</a> \
        # <a href="https://github.com/jezdez/dokku-postgres-plugin">PostgreSQL</a> \
        # <a href="https://github.com/jlachowski/dokku-pg-plugin">PostgreSQL</a> \
        # <a href="https://github.com/Kloadut/dokku-pg-plugin">PostgreSQL</a>"""

        for link in [link for link in BeautifulSoup(response, parse_only=SoupStrainer('a')) if link.name == 'a']:
            isOrg = False
            pluginAuthors = []
            if re.match('^\w+://.*github.com/[\w-]+?/[\w-]+?$', link['href']) and not re.match('.*progrium.*', link['href']):
                pluginUrl = link['href']
                pluginName = '%s' % (pluginUrl.split('/')[4])
                pluginOwner = '%s' % (pluginUrl.split('/')[3])
                pluginOwnerUrl = '%s/%s/%s/%s' % (pluginUrl.split('/')[0], pluginUrl.split('/')[1], pluginUrl.split('/')[2], pluginOwner)


                _, response = http.request(pluginOwnerUrl)
                for anchor in [link for link in BeautifulSoup(response, parse_only=SoupStrainer('a')) if link.name == 'a']:
                    try:
                        if 'org-module-link' in anchor['class']:
                            isOrg = True
                            peopleUrl = '%s/%s/%s/%s' % (pluginUrl.split('/')[0], pluginUrl.split('/')[1], pluginUrl.split('/')[2], anchor['href'])
                            _, response = http.request(peopleUrl)
                            for orgMemberLink in BeautifulSoup(response, parse_only=SoupStrainer('a', class_='member-link')).find_all(class_='member-username'):
                                pluginAuthors.append(orgMemberLink.text)
                    except KeyError:
                        continue

                if not isOrg:
                    pluginAuthors.append(pluginUrl.split('/')[3])

                try:
                    repoPluginTypes = self._getPluginTypes(pluginOwner, pluginName)
                except ApiNotFoundError:
                    status, _ = http.request(pluginUrl)
                    pluginOwner = status['content-location'].split('/')[3]
                    pluginName = status['content-location'].split('/')[4]
                    print "retrying contents: %s" % pluginName
                    try:
                        repoPluginTypes = self._getPluginTypes(pluginOwner, pluginName)
                    except ApiNotFoundError, e:
                        print "failed contents: %s, %s. %s" % (pluginUrl, pluginName, e)
                        repoPluginTypes = 'unknown'

                if pluginUrl not in [url for url in [plugin['url'] for plugin in self.plugins]]:
                    self.plugins.append({'name': pluginName, 'authors': pluginAuthors, 'ownerUrl': pluginOwnerUrl, 'url': pluginUrl, 'types': repoPluginTypes})

    def _getPluginTypes(self, owner, name):
        gh = GitHub(access_token=get_env_setting('GH_TOKEN'))
        try:
            _ = gh.repos(owner)(name).get()
        except ApiNotFoundError, e:
            raise e

        pluginRepoContents = gh.repos(owner)(name).contents().get()

        repoFiles = [item['path'] for item in pluginRepoContents if item['type'] == 'file']
        repoPluginTypes = [repoFile for repoFile in repoFiles if repoFile in self.pluginTypes]
        return repoPluginTypes

    def findPluginAuthor(self, pluginName):
        plugins = [plugin for plugin in self.plugins if pluginName == plugin['name']]
        return plugins

    def listPlugins(self, verbose=False):
        if verbose:
            plugins = self.plugins
        else:
            plugins = [plugin for plugin in self.plugins]

        return plugins

    def findPluginTypeAuthors(self, pluginType=None):
        plugins = []
        for plugin in self.plugins:
            if pluginType in plugin['types']:
                # print "%s in %s (%s)" % (pluginType, plugin['name'], ' '.join(plugin['types']))
                plugins.append(plugin)
        return plugins


def get_env_setting(setting):
    """ Get the environment setting or return exception """
    try:
        return environ[setting]
    except KeyError, e:
        error_msg = "Set the %s env variable" % setting
        print error_msg
        raise e


def main(args=None):
    if args is None:
        args = sys.argv[1:]

    parser = argparse.ArgumentParser()
    parser.add_argument('action', help='findauthors, list')
    parser.add_argument('--name', help='used to find plugin details by name')
    parser.add_argument('--type', help='used to find plugin details by type')
    parser.add_argument('--verbose', help='verbose output', action='store_true')
    args = parser.parse_args()

    dp = dokkuPlugins()
    if args.action == 'findauthors':
        if not args.name:
            parser.print_help()
            return 1
        plugins = dp.findPluginAuthor(pluginName=args.name)
        if plugins:
            table = [(plugin['url'], plugin['authors']) for plugin in plugins]
            print tabulate(table, ['url', 'authors'], tablefmt='simple')
        else:
            print 'error: %s plugin not found' % args.name

    if args.action == 'list':
        print tabulate(dp.listPlugins(verbose=args.verbose), headers='keys', tablefmt='simple')

    if args.action == 'findtypes':
        if not args.type:
            parser.print_help()
            return 1
        plugins = dp.findPluginTypeAuthors(pluginType=args.type)
        print tabulate(plugins, headers='keys', tablefmt='simple')

if __name__ == '__main__':
    sys.exit(main())
