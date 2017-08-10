import re
import sys
import os
import json
import optparse
import mimetypes
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


# <img> (attachments)
MACRO_IMAGE = """<ac:image>
<ri:attachment ri:filename="%s" />
</ac:image>
"""


# <img> (remote images)
MACRO_IMAGE_REMOTE = """<ac:image>
<ri:url ri:value="%s" /></ac:image>
"""


def create_popup(style, text):
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

    def block_popup(self, style, text):
        return create_popup(style, text)

    def image(self, src, title, text):
        if src.startswith('http'):
            rv = MACRO_IMAGE_REMOTE % src
        else:
            rv = MACRO_IMAGE % src
        return rv


class PopupBlockGrammar(mistune.BlockGrammar):
    block_popup = re.compile(r'^~([?!%])(.*?)\n', re.DOTALL)


class PopupBlockLexer(mistune.BlockLexer):
    """Support for "popups" in Markdown.

    Popups are block level elements that renders as Info/Note/Warning blocks in Confluence; the syntax is
    ~? for info popups, ~! for note and ~% for warnings.

    Example:

    ~?This is a INFO popup.
    """
    default_rules = ['block_popup'] + mistune.BlockLexer.default_rules

    def __init__(self, rules=None, **kwargs):
        if rules is None:
            rules = PopupBlockGrammar()
        super(PopupBlockLexer, self).__init__(rules, **kwargs)

    def parse_block_popup(self, m):
        style_symbol = m.group(1)
        if style_symbol == '?':
            style = 'info'
        elif style_symbol == '!':
            style = 'note'
        else:
            style = 'warning'

        self.tokens.append({
            'type': 'block_popup',
            'style': style,
            'text': m.group(2),
        })


class MarkdownWithPopup(mistune.Markdown):
    def __init__(self, renderer, **kwargs):
        if 'block' not in kwargs:
            kwargs['block'] = PopupBlockLexer
        super(MarkdownWithPopup, self).__init__(renderer, **kwargs)

    def output_block_popup(self):
        return self.renderer.block_popup(self.token['style'], self.token['text'])


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
        self.base_url = 'https://%s.atlassian.net' % self.domain
        renderer = ConfluenceRenderer()
        self.markdown = MarkdownWithPopup(renderer=renderer)

        self.session = requests.Session()
        self.session.auth = (self.username, self.password)
        self.session.headers = {
            'Content-Type': 'application/json'
        }

    def update_page(self, filename):
        with open(filename) as fd:
            meta, page_body_raw = extract_meta(fd.read())

        page_id = meta['id']
        page_title = meta['title']
        page_space = meta['space']

        response = self.session.get(
            '%s/wiki/rest/api/content/%s?expand=version,ancestors,body.storage' % (self.base_url, page_id))
        if response.status_code != 200:
            raise ConfluenceClientException("Error reading page: %r" % response)

        page_data = response.json()
        version = page_data['version']['number']

        # assemble the page
        warning_msg = create_popup('info', EDIT_WARNING)
        page_body_html = MACRO_TOC + warning_msg + self.markdown(page_body_raw)

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
        response = self.session.put('%s/wiki/rest/api/content/%s' % (self.base_url, page_id),
                                    data=json.dumps(payload))
        if response.status_code != 200:
            raise ConfluenceClientException("Error updating page: %r" % response)

        result = response.json()
        new_version = result['version']['number']
        link = result['_links']['base'] + result['_links']['webui']
        print "Updated page, version %d: %s" % (new_version, link)

    def upload_attachment(self, page_id, filename, comment=None):
        mimetype, _ = mimetypes.guess_type(filename)
        print "mimetype = %r" % mimetype
        basename = os.path.basename(filename)

        payload = {
            'comment': comment or '',
            'file': (basename, open(filename, 'rb'), mimetype, { 'Expires': 0 }),
        }

        old_attachment = self.get_attachment(page_id, filename)
        url = "%s/wiki/rest/api/content/%s/child/attachment/" % (self.base_url, page_id)
        if old_attachment is not None:
            url += "%s/data" % old_attachment['id']

        response = self.session.post(url, files=payload, headers={
            'X-Atlassian-Token': 'no-check',
            # We must delete the "default" content-type of this class... (application/json)
            'Content-Type': None,
        })
        if response.status_code != 200:
            raise ConfluenceClientException(
                "Error uploading attachment: %r (%r)" % (response, response.text))

    def get_attachment(self, page_id, filename):
        basename = os.path.basename(filename)
        response = self.session.get("%s/wiki/rest/api/content/%s/child/attachment?filename=%s" % (
            self.base_url, page_id, basename))
        if response.status_code == 404:
            return None
        elif response.status_code != 200:
            raise ConfluenceClientException("Error status code for `get_attachment`: %r" % response)

        data = response.json()
        results = data.get('results', [])
        if len(results):
            return results[0]
        return None


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
