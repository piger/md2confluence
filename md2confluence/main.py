import re
import sys
import os
import json
import optparse
import mistune
import requests


# Confluence macro to render a "Table of Contents".
MACRO_TOC = """<ac:structured-macro ac:name="toc">
<ac:parameter ac:name="printable">true</ac:parameter>
<ac:parameter ac:name="style">disc</ac:parameter>
<ac:parameter ac:name="maxLevel">5</ac:parameter>
<ac:parameter ac:name="minLevel">1</ac:parameter>
<ac:parameter ac:name="class">rm-contents</ac:parameter>
<ac:parameter ac:name="exclude"></ac:parameter>
<ac:parameter ac:name="type">list</ac:parameter>
<ac:parameter ac:name="outline">false</ac:parameter>
<ac:parameter ac:name="include"></ac:parameter>
</ac:structured-macro>
"""


# This message will appear on the top of each page created or updated with this script.
EDIT_WARNING = """<strong>NOTE</strong>: this page is managed with md2confluence:
any manual change to the contents of this page will be overwritten."""


# Info/Note/Warning blocks
MACRO_POPUP = """<p><ac:structured-macro ac:name="{type}"><ac:rich-text-body><p>
{contents}
</p></ac:rich-text-body></ac:structured-macro></p>
"""


def create_popup(text, style):
    assert style in ('info', 'warning', 'note')
    return MACRO_POPUP.format(type=style, contents=text)


class ConfluenceRenderer(mistune.Renderer):
    """A Markdown renderer that renders HTML compatible with Confluence "storage"
    format.
    """
    def block_code(self, code, lang):
        if not lang:
            lang = 'none'

        code_block = """<ac:structured-macro ac:name="code">
<ac:parameter ac:name="language">%s</ac:parameter>
<ac:plain-text-body><![CDATA[%s]]></ac:plain-text-body>
</ac:structured-macro>
""" % (lang, code)
        return code_block


def extract_meta(text):
    """Extract Meatdata headers from a Markdown document.

    From: https://github.com/lepture/mistune-contrib/blob/master/mistune_contrib/meta.py
    """
    indentation_re = re.compile(r'\n\s{2,}')
    meta_re = re.compile(r'^(\w+):\s*(.+?)\n')

    rv = {}
    m = meta_re.match(text)

    while m:
        key = m.group(1)
        value = m.group(2)
        value = indentation_re.sub('\n', value.strip())
        rv[key] = value
        text = text[len(m.group(0)):]
        m = meta_re.match(text)

    return rv, text


class ConfluenceClientException(Exception):
    pass


class ConfluenceClient(object):
    """A simple Confluence REST API client."""

    def __init__(self, username, password, domain):
        self.username = username
        self.password = password
        self.domain = domain
        self.base_url = 'https://%s.atlassian.net/wiki/rest/api/content/' % self.domain
        renderer = ConfluenceRenderer()
        self.markdown = mistune.Markdown(renderer=renderer)

    def update_page(self, filename):
        with open(filename) as fd:
            meta, page_body_raw = extract_meta(fd.read())

        page_id = meta['id']
        page_title = meta['title']
        page_space = meta['space']

        response = requests.get(
            '%s%s?expand=version,ancestors,body.storage' % (self.base_url, page_id),
            auth=(self.username, self.password))
        if response.status_code != 200:
            raise ConfluenceClientException("Error reading page: %r" % response)

        page_data = response.json()
        version = page_data['version']['number']

        # assemble the page
        warning_msg = create_popup(EDIT_WARNING, 'info')
        page_body_html = MACRO_TOC + warning_msg + self.markdown(page_body_raw)

        headers = {
            'Content-Type': 'application/json'
        }

        payload = {
            'id': page_id,
            'type': 'page',
            'title': page_title,
            'space': {
                'key': page_space,
            },
            'body': {
                'storage': {
                    'value': page_body_html,
                    'representation': 'storage',
                }
            },
            'version': {
                'number': version + 1,
            },
        }

        print "Updating page \"%s\"..." % page_title
        response = requests.put('%s%s' % (self.base_url, page_id), headers=headers,
                                data=json.dumps(payload), auth=(self.username, self.password))
        if response.status_code != 200:
            raise ConfluenceClientException("Error updating page: %r" % response)

        result = response.json()
        new_version = result['version']['number']
        link = result['_links']['base'] + result['_links']['webui']
        print "Updated page, version %d: %s" % (new_version, link)


def main():
    parser = optparse.OptionParser()
    opts, args = parser.parse_args()

    if len(args) < 1:
        print "Argument missing: filename"
        sys.exit(1)

    filename = args[0]

    username = os.getenv('JIRA_USERNAME')
    password = os.getenv('JIRA_PASSWORD')
    domain = os.getenv('JIRA_DOMAIN')

    if not username or not password or not domain:
        print "Please set JIRA_USERNAME, JIRA_PASSWORD and JIRA_DOMAIN."
        sys.exit(1)

    cli = ConfluenceClient(username, password, domain)
    cli.update_page(filename)


if __name__ == '__main__':
    main()
