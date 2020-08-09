from http_api import load_with_retry
import gzip, re, pyquery

ROOT_URL='https://www.sec.gov/'
BASE_EDGAR_URL= 'https://www.sec.gov/Archives/edgar/'
FULL_INDEX_URL= BASE_EDGAR_URL + 'full-index/'


def get_xbrl_link(f):
    report_url = BASE_EDGAR_URL + get_report_dir(f)
    url = report_url + f['file'] + "-index.html"
    index_page = load_with_retry(url)
    # print(url)
    index_page = pyquery.PyQuery(index_page)
    for tr in reversed(index_page('table tr')):
        tr = pyquery.PyQuery(tr)
        tds = tr('td')
        if len(tds) < 4:
            continue
        txt = pyquery.PyQuery(tds[1]).html()
        txt3 = pyquery.PyQuery(tds[3]).html()
        if txt is not None and ('XBRL INSTANCE DOCUMENT' in txt or 'EX-100.INS' in txt) \
                or txt3 is not None and ('EX-100.INS' in txt3 or 'EX-101.INS' in txt3):
            a = tr('a')[0]
            link = a.attrib['href']
            link = link.split('/')[-1]
            link = report_url + link
            if not link.lower().endswith('.xml'):
                continue
            return link
    print('missed', url, txt, txt3)
    return None


def load_report_list():
    for i in list_dirs():
        for f in load_xbrl_idx(*i):
            yield f


def list_dirs():
    year_idx = load_with_retry(FULL_INDEX_URL + 'index.xml')
    year_idx = pyquery.PyQuery(year_idx)
    year_idx = year_idx('item name[type=dir]')
    year_idx = [fid.text for fid in year_idx]
    for year in year_idx:
        print(year)
        quater_idx = load_with_retry(FULL_INDEX_URL + year + '/index.xml')
        quater_idx = pyquery.PyQuery(quater_idx)
        quater_idx = quater_idx('item name[type=dir]')
        quater_idx = [fid.text for fid in quater_idx]
        for quarter in quater_idx:
            print(quarter)
            yield (year, quarter)


def load_xbrl_idx(year, quater):
    idx = load_with_retry(FULL_INDEX_URL + year + '/' + quater + '/xbrl.gz')
    idx = gzip.decompress(idx)
    idx = idx.decode()
    idx = idx.split('\n')
    files = []
    for c in idx:
        m = re.match(r"^(.+)\|(.+)\|(.+)\|(.+)\|edgar/data/\d+/(.+).txt", c)
        if m:
            obj = dict(zip(
                ('cik', 'name', 'type', 'date', 'file'),
                (
                    m.group(1).strip(), m.group(2).strip(), m.group(3).strip(), m.group(4).strip(), m.group(5).strip(),)
            ))
            files.append(obj)
    files.sort(key=lambda f: f['date'] + "_" + f['cik'])
    return files


def get_report_dir(f):
    fid = f['file']
    fid_ = fid.replace('-', '')
    return 'data/' + f['cik'] + '/' + fid_ + "/"


if __name__ == '__main__':
    for f in load_report_list():
        print(f)