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

class PresidentElections(Elections):
    _president_elections_ids= {
        2004: 1001000882950,
        2008: 100100022176412,
        2012: 100100031793505,
        2018: 100100084849062
    }

    def __init__(self, year):
        self._url = self._get_gas_url_by_year(year)

    def _get_gas_url_by_year(self, year):
        if year not in self._president_elections_ids:
            return None

        president_url_part = "/region/izbirkom?action=show&global=1&vrn={}&region=0&prver=0&pronetvd=null".format(self._president_elections_ids[year])
        return self.base_url + president_url_part
    
    def get_candidates(self):
        return Candidates(self._url)
    
    def get_final_results(self):
        return FinalResults(self._url)

    def get_url(self):
        return self._url
    
class Candidates:
    def __init__(self, elections_url):
        self._urls = self._get_all_candidates_pages_urls(self._get_candidates_first_url(elections_url))

    def _get_candidates_first_url(self, elections_url):
        soup = get_soup(elections_url)
        a = soup.find('a', href=True, text="Сведения о кандидатах на должность Президента Российской Федерации")
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

class FinalResults:
    def __init__(self, elections_url):
        self._url_parts = {}
        self._sum_url = self._get_sum_url(elections_url)
        self._params_list = ['listed_voters', 'got_ballots_by_uik', 
            'issued_ballots_early_voters', 'issued_ballots_elections_day_inside', 
            'issued_ballots_elections_day_outside', 'canceled_ballots',
            'ballots_in_portable_boxes', 'ballots_in_stationary_boxes', 'valid_ballots', 'invalid_ballots', 'candidates']
        self._params = self._get_params()

    def _get_sum_url(self, elections_url):
        soup = get_soup(elections_url)
        a = soup.find('a', href=True, text="Сводная таблица результатов выборов")
        if not a:
            a = soup.find('a', href=True, text="Сводная таблица о результатах выборов")

        return a['href']
    
    def _get_row_data(self, row):
        return list(map(lambda td: int(td.text), row.find_all("td")))

    def _add_candiadates_data(self, regions, trs):
        # regions['candidates'] = []
        for index, region in enumerate(regions):
            regions[index]['candidates'] = {}
        for candidate_row_number, candidate_name in self._params['candidates'].items():
            candidate_row_data = []
            for td in trs[candidate_row_number].find_all("td"):
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
                area_data.append(area_item)
            area_data = self._add_params_data(area_data, self._params_list, soup)
            return area_data
        else:
            area_item = self._get_left_table_data(url)
            # area_item['name'] = region_name
            area_item['url'] = url
            return [area_item, ]

    def _get_tik_real_url(self, first_tik_url):
        soup = get_soup(first_tik_url)
        a = soup.find('a', href=True, text="сайт избирательной комиссии субъекта Российской Федерации")
        return a['href']        

    def _get_left_table_data(self, url):
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
        for tr in tbl.find_all("tr"):
            tds = tr.find_all("td")
            number_td = tds[0]
            caption_td = tds[1]
            if caption_td:
                caption = caption_td.text.strip()
                if candidate_flag:
                    params['candidates'][counter] = caption
                if caption in ('Число избирателей, включенных в список избирателей',
                    'Число избирателей, включенных в списки избирателей',
                    'Число избирателей, внесенных в список'):
                    params['listed_voters'] = counter
                if caption in ('Число избирательных бюллетеней, полученных участковой избирательной комиссией',
                    'Число избирательных бюллетеней, полученных участковыми избирательными комиссиями',
                    'Число полученных избирательных бюллетеней'):
                    params['got_ballots_by_uik'] = counter
                if caption in ('Число избирательных бюллетеней, выданных избирателям, проголосовавшим досрочно',
                    'Число избирательных бюллетеней, выданных досрочно',
                    'Число избирательных бюллетеней, выданных  досрочно'):
                    params['issued_ballots_early_voters'] = counter
                if caption in ('Число избирательных бюллетеней, выданных в помещении для голосования в день голосования',
                    'Число избирательных бюллетеней, выданных в помещениях для голосования в день голосования',
                    'Число избирательных бюллетеней, выданных в день голосования'):
                    params['issued_ballots_elections_day_inside'] = counter
                if caption in ('Число избирательных бюллетеней, выданных вне помещения для голосования в день голосования',
                    'Число избирательных бюллетеней, выданных вне помещений для голосования в день голосования',
                    'Число избирательных бюллетеней, выданных вне помещения'):
                    params['issued_ballots_elections_day_outside'] = counter
                if caption == 'Число погашенных избирательных бюллетеней':
                    params['canceled_ballots'] = counter
                if caption in ('Число избирательных бюллетеней в переносных ящиках для голосования',
                    'Число избирательных бюллетеней в переносных ящиках'):
                    params['ballots_in_portable_boxes'] = counter
                if caption == 'Число бюллетеней в стационарных ящиках для голосования':
                    params['ballots_in_stationary_boxes'] = counter
                if caption == 'Число недействительных избирательных бюллетеней':
                    params['invalid_ballots'] = counter
                if caption == 'Число действительных избирательных бюллетеней':
                    params['valid_ballots'] = counter
            if tr.text.strip() in ("", "Число голосов избирателей, поданных за каждый список"):
                candidate_flag = True
            counter += 1
        return params
    
    def get_url(self):
        return self._sum_url

if __name__ == "__main__":
    elect = PresidentElections(2004)
    fres = elect.get_final_results()
    # print(fres.get_summary())
    # print(fres.get_regions()[0])
    regions = fres.get_regions()
    regions_counter = 0
    regions_number = len(regions)
    tiks = []
    uiks = []
    for region in regions:
        tmp_tiks = fres.get_tiks_by_region_url(region['url'])
        tiks.extend(tmp_tiks)
        for tik in tmp_tiks:
            uiks.extend(fres.get_uiks_by_tik_url(tik['url']))
        regions_counter += 1
        print("[{}/{}]{}".format(regions_counter, regions_number, region['name']))
        if regions_counter > 3:
            break
    print(len(tiks))
    # print(tiks[0])
    print(len(uiks))
    print(uiks[0])
