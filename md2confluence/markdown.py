import re
import pkg_resources
import mistune


SNIPPETS = {
    # warning message to prepend to every page
    'edit_warning': 'data/edit_warning.html',

    # confluence macro for a Table of Contents
    'toc': 'data/toc.xml',

    # confluence macro for "popups"
    # arg 'type': one of: info, note, warning.
    # arg 'contents': popup text body
    'popup': 'data/popup.xml',

    # image (attachment)
    # arg 'filename': filename of the attachment file
    'image_attachment': 'data/image_attachment.xml',

    # image (remote URL)
    # arg 'url': url of the remote image
    'image_url': 'data/image_remote.xml',

    # code block
    # arg 'lang': language (for syntax highlighting)
    # arg 'contents': contents of the code snippet
    'code': 'data/code.xml',
}


def get_snippet(name):
    """Render "XHTML" (or rather XML) blocks in Confluence "storage" syntax"""

    return pkg_resources.resource_string('md2confluence', SNIPPETS[name])


def create_popup(style, text):
    """Create a block popup"""

    assert style in ('info', 'warning', 'note')
    return get_snippet('popup').format(type=style, contents=text)


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


class ConfluenceRenderer(mistune.Renderer):
    """A Markdown renderer that renders HTML compatible with Confluence "storage"
    format.
    """
    def block_code(self, code, lang):
        if not lang:
            lang = 'none'
        return get_snippet('code').format(lang=lang, contents=code)

    def block_popup(self, style, text):
        return create_popup(style, text)

    def image(self, src, title, text):
        if src.startswith('http'):
            rv = get_snippet('image_url').format(url=src)
        else:
            rv = get_snippet('image_attachment').format(filename=src)
        return rv


class PopupBlockGrammar(mistune.BlockGrammar):
    block_popup = re.compile(r'^~([?!%])(.*?)\n', re.DOTALL)


class PopupBlockLexer(mistune.BlockLexer):
    """Support for "popups" in Markdown.

    Popups are block level elements that renders as Info/Note/Warning blocks in Confluence; the
    syntax is ~? for info popups, ~! for note and ~% for warnings.

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
    def __init__(self, **kwargs):
        if 'block' not in kwargs:
            kwargs['block'] = PopupBlockLexer
        renderer = ConfluenceRenderer()
        super(MarkdownWithPopup, self).__init__(renderer, **kwargs)

    def output_block_popup(self):
        return self.renderer.block_popup(self.token['style'], self.token['text'])
