import re
import sys
import os
import json
import optparse
import mimetypes
import requests
from md2confluence.markdown import MarkdownWithPopup, extract_meta, create_popup, get_snippet


class ConfluenceClientException(Exception):
    pass


class APIError(ConfluenceClientException):
    def __init__(self, msg, response):
        super(APIError, self).__init__(msg)
        self.response = response


class ConfluenceClient(object):
    """A simple Confluence REST API client."""

    def __init__(self, username, password, domain):
        self.username = username
        self.password = password
        self.domain = domain
        self.base_url = 'https://%s.atlassian.net' % self.domain
        self.markdown = MarkdownWithPopup()

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

        response = self.session.get("%s/wiki/rest/api/content/%s"
                                    "?expand=version,ancestors,body.storage" % (
                                        self.base_url, page_id))
        if response.status_code != 200:
            raise APIError("Error reading page %s" % page_id, response)

        page_data = response.json()
        version = page_data['version']['number']

        # assemble the page
        warning_msg = create_popup('info', get_snippet('edit_warning'))
        page_body_html = get_snippet('toc') + warning_msg + self.markdown(page_body_raw)
        attachments = self._extract_attachments(page_body_html)

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
            raise APIError("Error updating page: %s" % page_id, response)

        result = response.json()
        new_version = result['version']['number']
        link = result['_links']['base'] + result['_links']['webui']
        print "Updated page %s \"%s\", version %d: %s" % (page_id, page_title, new_version, link)

        if not attachments:
            return

        for attachment in attachments:
            if os.path.exists(attachment):
                print "Uploading attachment: \"%s\"" % attachment
                self.upload_attachment(page_id, attachment)

    def upload_attachment(self, page_id, filename, comment=None):
        mimetype, _ = mimetypes.guess_type(filename)
        basename = os.path.basename(filename)

        payload = {
            'comment': comment or '',
            'file': (basename, open(filename, 'rb'), mimetype, {'Expires': 0}),
        }

        old_attachment = self.get_attachment(page_id, filename)
        url = "%s/wiki/rest/api/content/%s/child/attachment/" % (self.base_url, page_id)
        if old_attachment is not None:
            url += "%s/data" % old_attachment['id']

        response = self.session.post(url, files=payload, headers={
            'X-Atlassian-Token': 'no-check',
            # Here we must let requests set the correct content type for a file upload, instead of
            # using our default "application/json"
            'Content-Type': None,
        })
        if response.status_code != 200:
            raise APIError("Error uploading attachment: %s" % filename, response)

    def get_attachment(self, page_id, filename):
        basename = os.path.basename(filename)
        response = self.session.get("%s/wiki/rest/api/content/%s/child/attachment?filename=%s" % (
            self.base_url, page_id, basename))
        if response.status_code == 404:
            return None
        elif response.status_code != 200:
            raise APIError("Error getting attachment: %s" % filename, response)

        data = response.json()
        results = data.get('results', [])
        if len(results):
            return results[0]
        return None

    def _extract_attachments(self, page):
        return re.findall(r'<ri:attachment ri:filename="([^"]+)" />', page)


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
    try:
        cli.update_page(filename)
    except APIError as ex:
        print "API Error: %s" % ex
        print "HTTP %d: %s" % (ex.response.status_code, ex.response.text)


if __name__ == '__main__':
    main()
