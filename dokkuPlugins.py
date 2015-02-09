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


def get_env_setting(setting):
    """ Get the environment setting or return exception """
    try:
        return environ[setting]
    except KeyError, e:
        error_msg = "Set the %s env variable" % setting
        print error_msg
        raise e


class dokkuPlugins(object):

    @classmethod
    def __init__(cls, testing=False):
        cls.known_plugin_types = ['backup-check', 'backup-export', 'backup-import', 'bind-external-ip', 'check-deploy', 'commands', 'dependencies',
                                  'docker-args', 'docker-args-build', 'docker-args-deploy', 'docker-args-run', 'git-post-pull', 'git-pre-pull',
                                  'install', 'nginx-hostname', 'nginx-pre-reload', 'post-build', 'post-build-buildstep', 'post-build-dockerfile',
                                  'post-delete', 'post-deploy', 'post-domains-update', 'post-release', 'post-release-buildstep', 'post-release-dockerfile',
                                  'pre-build', 'pre-build-buildstep', 'pre-build-dockerfile', 'pre-delete', 'pre-deploy', 'pre-release', 'pre-release-buildstep',
                                  'pre-release-dockerfile', 'receive-app', 'update']
        cls.plugins = []
        cls.http = httplib2.Http()
        cls.gh = GitHub(access_token=get_env_setting('GH_TOKEN'))

        print 'Retrieving dokku plugin metadata...\n'

        if testing:
            response = """<a href="https://github.com/F4-Group/dokku-apt">APT</a> \
                        <a href="https://github.com/blag/dokku-elasticsearch-plugin">dokku-elasticsearch-plugin</a> \
                        <a href="https://github.com/jezdez/dokku-postgres-plugin">PostgreSQL</a> \
                        <a href="https://github.com/jlachowski/dokku-pg-plugin">PostgreSQL</a> \
                        <a href="https://github.com/Kloadut/dokku-pg-plugin">PostgreSQL</a> \
                        <a href="https://github.com/ohardy/dokku-mariadb">MariaDB</a>"""
        else:
            _, response = cls.http.request('http://progrium.viewdocs.io/dokku/plugins')

        for link in [link for link in BeautifulSoup(response, parse_only=SoupStrainer('a')) if link.name == 'a']:
            if re.match('^\w+://.*github.com/[\w-]+?/[\w-]+?$', link['href']) and not re.match('.*progrium.*', link['href']):
                plugin_url = link['href']
                plugin_name = '%s' % (plugin_url.split('/')[4])
                plugin_owner = '%s' % (plugin_url.split('/')[3])
                plugin_owner_url = '%s/%s/%s/%s' % (plugin_url.split('/')[0], plugin_url.split('/')[1], plugin_url.split('/')[2], plugin_owner)
                plugin_repo_metadata = cls._gh_repo_metadata(plugin_owner, plugin_name, plugin_url)

                if plugin_repo_metadata['owner']['type'] == 'Organization':
                    organization_members_metadata = cls._gh_org_members(plugin_repo_metadata['owner']['login'])
                    pluginAuthors = [member['login'] for member in organization_members_metadata if member['type'] == 'User']
                else:
                    pluginAuthors = [plugin_url.split('/')[3]]

                repo_plugin_types = cls._plugin_types(plugin_owner, plugin_name, plugin_url)

                if plugin_url not in [url for url in [plugin['url'] for plugin in cls.plugins]]:
                    cls.plugins.append({'name': plugin_name, 'authors': pluginAuthors, 'ownerUrl': plugin_owner_url, 'url': plugin_url, 'types': repo_plugin_types})

    @classmethod
    def _plugin_types(cls, owner, repo_name, repo_url):
        try:
            repo_contents = cls._gh_repo_contents(owner, repo_name, repo_url)
        except ApiNotFoundError, e:
            raise e

        repo_files = [item['path'] for item in repo_contents if item['type'] == 'file']
        repo_plugin_types = [repo_file for repo_file in repo_files if repo_file in cls.known_plugin_types]
        return repo_plugin_types

    @classmethod
    def _gh_org_members(cls, owner):
        org_metadata = cls.gh.orgs(owner).members.get()
        return org_metadata

    @classmethod
    def _gh_repo_metadata(cls, owner, repo_name, repo_url):
        try:
            repo_metadata = cls.gh.repos(owner)(repo_name).get()
        except ApiNotFoundError, e:
            status, _ = cls.http.request(repo_url)
            owner = status['content-location'].split('/')[3]
            repo_name = status['content-location'].split('/')[4]
            try:
                repo_metadata = cls.gh.repos(owner)(repo_name).get()
            except ApiNotFoundError, e:
                print "failed contents: %s, %s. %s" % (repo_url, repo_name, e)
                raise e

        return repo_metadata

    @classmethod
    def _gh_repo_contents(cls, owner, repo_name, repo_url):
        try:
            repo_contents = cls.gh.repos(owner)(repo_name).contents().get()
        except ApiNotFoundError, e:
            status, _ = cls.http.request(repo_url)
            owner = status['content-location'].split('/')[3]
            repo_name = status['content-location'].split('/')[4]
            try:
                repo_contents = cls.gh.repos(owner)(repo_name).contents().get()
            except ApiNotFoundError, e:
                print "failed contents: %s, %s. %s" % (repo_url, repo_name, e)
                raise e

        return repo_contents

    @classmethod
    def findPluginAuthor(cls, plugin_name):
        plugins = [plugin for plugin in cls.plugins if plugin_name == plugin['name']]
        return plugins

    @classmethod
    def listPlugins(cls):
        return cls.plugins

    @classmethod
    def findPluginTypeAuthors(cls, plugin_types):
        plugins = []
        for plugin in cls.plugins:
            # print "checking for %s in %s" % (plugin_types, plugin['types'])
            for plugin_type in plugin_types:
                if plugin_type in plugin['types']:
                    # print "%s in %s (%s)" % (plugin_types, plugin['name'], ' '.join(plugin['types']))
                    plugins.append(plugin)
        return plugins


def main(args=None):
    if args is None:
        args = sys.argv[1:]

    parser = argparse.ArgumentParser()
    parser.add_argument('--name', help='used to find plugin details by name')
    parser.add_argument('--types', help='used to find plugin details by type')
    parser.add_argument('--short', help='short output', action='store_true')
    parser.add_argument('--testing', help='use testing response', action='store_true')
    args = parser.parse_args()

    dp = dokkuPlugins(testing=args.testing)
    short_headers = ['url', 'authors']

    if args.name:
        plugins = dp.findPluginAuthor(plugin_name=args.name)
    elif args.types:
        plugins = dp.findPluginTypeAuthors(plugin_types=args.types.split(','))
        short_headers = ['url', 'types', 'authors']
    else:
        plugins = dp.listPlugins()

    if plugins:
        if args.short:
            # table = [(plugin[short_headers[0]], plugin[short_headers[1]]) for plugin in plugins]
            table = [[plugin[header] for header in short_headers] for plugin in plugins]
            print tabulate(table, short_headers, tablefmt='simple')
        else:
            print tabulate(plugins, headers='keys', tablefmt='simple')
        return 0
    else:
        print 'error: no plugins were found'
        return 1


if __name__ == '__main__':
    sys.exit(main())
