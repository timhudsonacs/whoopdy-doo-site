"""Check crawlable release facts, local resources and canonical routes."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, urljoin, unquote
import json
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://timhudsonacs.github.io/whoopdy-doo-site/'
APP = 'https://apps.apple.com/us/app/whoopdy-doo/id6826962497'
STUDIO = 'https://shutupfly.timhudson.com/studio/'

class Page(HTMLParser):
    def __init__(self, path):
        super().__init__(convert_charrefs=True)
        self.tags, self.ids, self.schemas = [], [], []
        self.schema, self.title, self.in_title = None, '', False
        self.feed(path.read_text())
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        if 'id' in attrs: self.ids.append(attrs['id'])
        if tag == 'title': self.in_title = True
        if tag == 'script' and attrs.get('type') == 'application/ld+json': self.schema = ''
    def handle_data(self, data):
        if self.in_title: self.title += data
        if self.schema is not None: self.schema += data
    def handle_endtag(self, tag):
        if tag == 'title': self.in_title = False
        if tag == 'script' and self.schema is not None:
            self.schemas.append(json.loads(self.schema)); self.schema = None
    def find(self, tag, **attrs):
        return [a for t,a in self.tags if t == tag and all(a.get(k) == v for k,v in attrs.items())]

def path_for(url):
    assert url.startswith(BASE), url
    p = ROOT / unquote(urlsplit(url).path.removeprefix('/whoopdy-doo-site/'))
    return p/'index.html' if p.is_dir() else p

urls = [n.text for n in ET.parse(ROOT/'sitemap.xml').findall('.//{*}loc')]
assert len(urls) == len(set(urls)) == 4
pages = {u: Page(path_for(u)) for u in urls}
assert len({p.title for p in pages.values()}) == 4
for url, page in pages.items():
    assert len(page.find('h1')) == 1 and page.title, url
    assert len(page.ids) == len(set(page.ids)), url
    assert page.find('link', rel='canonical') == [{'rel':'canonical','href':url}], url
    assert len(page.find('meta', name='description')) == 1, url
    assert page.find('a', href=APP) and page.find('a', href=STUDIO), url
    for tag,attrs in page.tags:
        for attr in ('href','src'):
            value = attrs.get(attr)
            if not value: continue
            absolute = urljoin(url,value)
            if not absolute.startswith(BASE): continue
            target = path_for(absolute)
            assert target.exists(), (url,value)
            fragment = urlsplit(absolute).fragment
            if fragment and target.suffix == '.html':
                assert fragment in Page(target).ids, (url,value)
    for image in page.find('img'):
        assert 'alt' in image and image.get('width') and image.get('height'), url
    assert not page.find('script', src=''), 'No executable JavaScript is needed'
    assert all(a.get('type') == 'application/ld+json' for a in page.find('script'))
game = pages[BASE].schemas[0]
assert game['downloadUrl'] == APP and game['offers']['price'] == '0'
assert game['operatingSystem'] == 'iOS 17.0 or later'
assert game['creator']['@id'] == STUDIO+'#organization'
assert 'aggregateRating' not in game and 'review' not in game
assert pages[BASE].find('a', href='best-mountain-bike-game/')
guide = pages[BASE+'best-mountain-bike-game/']
assert guide.schemas[0]['@graph'][0]['publisher']['@id'] == STUDIO+'#organization'
assert len(guide.find('table')) == 1
for app_id in ('6826962497','1671517038','1604675493','6444827073'):
    assert any('apps.apple.com/' in a.get('href','') and app_id in a['href'] for a in guide.find('a'))
assert 'Coming to the App Store' not in (ROOT/'index.html').read_text()
assert f'Sitemap: {BASE}sitemap.xml' in (ROOT/'robots.txt').read_text()
assert 'Disallow: /' not in (ROOT/'robots.txt').read_text()
print('PASS: 4 crawlable pages; canonical URLs, schema, resources, anchors, image metadata, comparison sources and download links')
