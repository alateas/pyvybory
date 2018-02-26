from bs4 import BeautifulSoup
import urllib.request
from urllib.parse import urlparse, parse_qs

def get_soup(url):
    with urllib.request.urlopen(url) as response:
        html = response.read()

    return BeautifulSoup(html.decode("cp1251"), 'html.parser')

def get_url_param(url, name):
    return parse_qs(urlparse(url).query)[name][0]

class Elections:
    base_url = "http://www.vybory.izbirkom.ru"

    def __init__(self, year):
        self._url = self._get_gas_url_by_year(year)

    def _get_gas_url_by_year(self, year):
        if year not in self._vrn_ids:
            return None

        tail_url_part = "/region/izbirkom?action=show&global=1&vrn={}&region=0&prver=0&pronetvd=null".format(self._vrn_ids[year])
        return self.base_url + tail_url_part
    
    def get_candidates(self):
        return Candidates(self._url)
    
    def get_final_results(self):
        return FinalResults(self._url)

    def get_url(self):
        return self._url


class PresidentElections(Elections):
    _vrn_ids= {
        2004: 1001000882950,
        2008: 100100022176412,
        2012: 100100031793505,
        2018: 100100084849062
    }

    def get_candidates(self):
        return PresidentCandidates(self._url)
    
    def get_final_results(self):
        return PresidentFinalResults(self._url)


class DumaElections(Elections):
    _vrn_ids= {
        # 2003: 100100095619,
        # Другой формат, пока не реализовано
        2007: 100100021960181,
        2011: 100100028713299,
        2016: 100100067795849
    }

    def get_candidates(self):
        # Not implemented yet
        return None
    
    def get_final_results(self):
        return DumaFinalResults(self._url)


class Candidates:
    first_url_text = ""

    def __init__(self, elections_url):
        self._urls = self._get_all_candidates_pages_urls(self._get_candidates_first_url(elections_url))

    def _get_candidates_first_url(self, elections_url):
        soup = get_soup(elections_url)
        a = soup.find('a', href=True, text=self.first_url_text)
        return a['href']

    def _get_candidates_by_url(self, url):
        soup = get_soup(url)
        tbody = soup.find(id="table-1").find("tbody")
        t = tbody.find_all('a')
        return list(map(lambda x: x.string, t))

    def _get_all_candidates_pages_urls(self, first_url):
        soup = get_soup(first_url)
        td = soup.find_all('table')[1].find_all("td")[-1]
        return [first_url] + list(map(lambda x: x['href'], td.find_all('a')))

    def get_all_candidates(self):
        candidates = []
        for u in self._urls:
            candidates.extend(self._get_candidates_by_url(u))
        return candidates

class PresidentCandidates(Candidates):
    first_url_text = "Сведения о кандидатах на должность Президента Российской Федерации"

class FinalResults:
    _sum_url_texts = []

    def __init__(self, elections_url):
        self._url_parts = {}
        self._sum_url = self._get_sum_url(elections_url)
        self._params_list = ['listed_voters', 'got_ballots_by_uik', 
            'issued_ballots_early_voters', 'issued_ballots_elections_day_inside', 
            'issued_ballots_elections_day_outside', 'canceled_ballots',
            'ballots_in_portable_boxes', 'ballots_in_stationary_boxes', 'valid_ballots', 'invalid_ballots', 'candidates']
        self._params = self._get_params()

    def _find_one_of_a(self, soup, texts):
        for t in texts:
           a = soup.find('a', href=True, text=t)
           if a:
               return a
        return None

    def _get_sum_url(self, elections_url):
        soup = get_soup(elections_url)
        a = self._find_one_of_a(soup, self._sum_url_texts)
        if a:
            return a['href']
    
    def _get_row_data(self, row):
        return list(map(lambda td: int(td.text), row.find_all("td")))

    def _add_candiadates_data(self, regions, trs):
        row_correction = len(trs) - self._trs_count
        for index, region in enumerate(regions):
            regions[index]['candidates'] = {}
        for candidate_row_number, candidate_name in self._params['candidates'].items():
            candidate_row_data = []
            for td in trs[candidate_row_number + row_correction].find_all("td"):
                candidate_data = {}
                b = td.find("b")
                candidate_data['votes'] = int(b.text)
                candidate_data['percents'] = float(td.find("br").nextSibling.strip().strip('%'))
                
                candidate_row_data.append(candidate_data)
            for index, region in enumerate(regions):
                regions[index]['candidates'][candidate_name] = candidate_row_data[index]

        return regions

    def _add_params_data(self, regions, params_list, soup):
        table = soup.find("table", {"style" : "width:100%;overflow:scroll"})
        trs = table.find_all('tr')
        for param in params_list:
            if param == 'candidates':
                regions = self._add_candiadates_data(regions, trs)
            else:
                row_data = self._get_row_data(trs[self._params[param]])
                for index, region in enumerate(regions):
                    regions[index][param] = row_data[index]
        return regions

    def _get_area_data(self, url, is_tik_url=False):
        if is_tik_url:
            url = self._get_tik_real_url(url) 
        soup = get_soup(url)
        table = soup.find("table", {"style" : "width:100%;overflow:scroll"})
        if table and table.text.strip() != "":
            trs = table.find_all('tr')
            tds = trs[0].find_all('td')
            area_data = []
            for td in tds:
                area_item = {}
                area_item['name'] = td.text
                a = td.find('a')
                if a:
                    area_item['url'] = a['href']
                else:
                    if not is_tik_url:
                        area_item = self._get_left_table_data(url, True)
                        area_item['url'] = url
                        return [area_item, ]
                area_data.append(area_item)
            area_data = self._add_params_data(area_data, self._params_list, soup)
            return area_data
        else:
            area_item = self._get_left_table_data(url, True)
            area_item['url'] = url
            return [area_item, ]

    def _get_tik_real_url(self, first_tik_url):
        soup = get_soup(first_tik_url)
        a_tag = soup.find('a', href=True, text="сайт избирательной комиссии субъекта Российской Федерации")
        if a_tag:
            href = a_tag.get('href')
        return href

    def _get_left_table_data(self, url, get_name = False):
        soup = get_soup(url)
        table = soup.find("td", {'align': 'left', 'style': 'height:100%;', 'valign': 'top'}).find("table")
        res = {}
        trs = table.find_all("tr")
        for param in self._params_list:
            if param == "candidates":
                res['candidates'] = {}
                for candidate_row_number, candidate_name in self._params['candidates'].items():
                    candidate_data = {}
                    td = trs[candidate_row_number].find_all("td")[2]
                    b = td.find("b")
                    candidate_data['votes'] = int(b.text)
                    candidate_data['percents'] = float(td.find("br").nextSibling.strip().strip('%'))
                    res['candidates'][candidate_name] = candidate_data
            else:
                res[param] = int(trs[self._params[param]].find_all("td")[2].text)
        if get_name:
            name_tr = soup.find("tr", {"bgcolor": "eeeeee"})
            res['name'] = name_tr.find_all("td")[1].text
        return res
        
    def _append_tik_data(self, data_set, tik_index, region_id, tik_id):
        data_set[tik_index]['uiks'] = self._get_tik_data(region_id, tik_id)

    def get_summary(self):
        return self._get_left_table_data(self._sum_url)

    def get_regions(self):
        return self._get_area_data(self._sum_url)

    def get_tiks_by_region_url(self, region_url):
        return self._get_area_data(region_url)
    
    def get_uiks_by_tik_url(self, tik_url):
        return self._get_area_data(tik_url, True)

    def _get_params(self):
        soup = get_soup(self._sum_url)
        tbl = soup.find("td", {'align': 'left', 'style': 'height:100%;', 'valign': 'top'}).find("table")
        counter = 0
        params = {}
        params['candidates'] = {}
        candidate_flag = False
        trs = tbl.find_all("tr")
        self._trs_count = len(trs)
        for tr in trs:
            tds = tr.find_all("td")
            number_td = tds[0]
            caption_td = tds[1]
            if caption_td:
                caption = caption_td.text.strip()
                if candidate_flag:
                    params['candidates'][counter] = caption
                if caption in ('Число избирателей, включенных в список избирателей',
                    'Число избирателей, включенных в списки избирателей',
                    'Число избирателей, внесенных в список',
                    'Число избирателей, внесенных в списки',
                    'Число избирателей, внесенных в список избирателей на момент окончания голосования',
                    'Число избирателей, внесенных в списки избирателей',
                    'Число избирателей, внесенных в список избирателей'):
                    params['listed_voters'] = counter
                if caption in ('Число избирательных бюллетеней, полученных участковой избирательной комиссией',
                    'Число избирательных бюллетеней, полученных участковыми избирательными комиссиями',
                    'Число полученных избирательных бюллетеней',
                    'Число бюллетеней, полученных участковыми комиссиями'):
                    params['got_ballots_by_uik'] = counter
                if caption in ('Число избирательных бюллетеней, выданных избирателям, проголосовавшим досрочно',
                    'Число избирательных бюллетеней, выданных досрочно',
                    'Число избирательных бюллетеней, выданных  досрочно',
                    'Число бюллетеней, выданных избирателям, проголосовавшим досрочно',):
                    params['issued_ballots_early_voters'] = counter
                if caption in ('Число избирательных бюллетеней, выданных в помещении для голосования в день голосования',
                    'Число избирательных бюллетеней, выданных в помещениях для голосования в день голосования',
                    'Число избирательных бюллетеней, выданных в день голосования',
                    'Число бюллетеней, выданных избирателям на избирательном участке',
                    'Число избирательных бюллетеней, выданных избирателям в помещении для голосования',
                    'Число избирательных бюллетеней, выданных избирателям в помещениях для голосования'):
                    params['issued_ballots_elections_day_inside'] = counter
                if caption in ('Число избирательных бюллетеней, выданных вне помещения для голосования в день голосования',
                    'Число избирательных бюллетеней, выданных вне помещений для голосования в день голосования',
                    'Число избирательных бюллетеней, выданных вне помещения',
                    'Число бюллетеней, выданных избирателям, проголосовавшим вне помещения для голосования',
                    'Число избирательных бюллетеней, выданных избирателям вне помещения для голосования',
                    'Число избирательных бюллетеней, выданных избирателям вне помещений для голосования'):
                    params['issued_ballots_elections_day_outside'] = counter
                if caption in ['Число погашенных избирательных бюллетеней',
                    'Число погашенных бюллетеней']:
                    params['canceled_ballots'] = counter
                if caption in ('Число избирательных бюллетеней в переносных ящиках для голосования',
                    'Число избирательных бюллетеней в переносных ящиках',
                    'Число бюллетеней в переносных ящиках для голосования',
                    'Число избирательных бюллетеней, содержащихся в переносных ящиках для голосования'):
                    params['ballots_in_portable_boxes'] = counter
                if caption in  ('Число бюллетеней в стационарных ящиках для голосования',
                    'Число бюллетеней в стационарных ящиках для голосования',
                    'Число избирательных бюллетеней, содержащихся в стационарных ящиках для голосования',
                    'Число избирательных бюллетеней в стационарных ящиках для голосования'):
                    params['ballots_in_stationary_boxes'] = counter
                if caption in ('Число недействительных избирательных бюллетеней',
                    'Число недействительных бюллетеней'):
                    params['invalid_ballots'] = counter
                if caption in ('Число действительных избирательных бюллетеней',
                    'Число действительных бюллетеней'):
                    params['valid_ballots'] = counter
            if tr.text.strip() in ("", "Число голосов избирателей, поданных за каждый список"):
                candidate_flag = True
            counter += 1
        return params
    
    def get_url(self):
        return self._sum_url

class PresidentFinalResults(FinalResults):
    _sum_url_texts = ("Сводная таблица результатов выборов", "Сводная таблица о результатах выборов")

class DumaFinalResults(FinalResults):
    _sum_url_texts = ("Сводная таблица итогов голосования по федеральному округу",
        "Сводная таблица результатов выборов",
        "Сводная таблица результатов выборов по федеральному избирательному округу")
