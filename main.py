from lxml.html import fromstring
import requests
from itertools import cycle, islice
from fake_useragent import UserAgent
from bs4 import BeautifulSoup
from collections import defaultdict
import csv
import datetime

from pprint import pprint

header = ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

def get_proxies():
    url = 'https://free-proxy-list.net/'
    response = requests.get(url)
    parser = fromstring(response.text)
    proxies = set()
    for i in parser.xpath('//tbody/tr'):
        if i.xpath('.//td[7][contains(text(),"yes")]'):
            proxy = ":".join([i.xpath('.//td[1]/text()')[0], i.xpath('.//td[2]/text()')[0]])
            proxies.add(proxy)
    return proxies

def get_page_content(url, proxy_pool, expected_tag, tag_filter):
    for index, proxy in enumerate(proxy_pool):
        try:
          ua = UserAgent()
          headers = {'User-Agent': ua.random}
          print(f"trying to get url: {url}")
          response = requests.get(url, headers=headers, proxies={"http": proxy, "https": proxy}, timeout=5)
          print(response.text)
          print("status code is:")
          print(response.status_code)
          soup = BeautifulSoup(response.text, "html.parser")
          filtered_content = soup.findAll(expected_tag, **tag_filter)
          print(filtered_content)
          if filtered_content:
            print(f"{expected_tag} found on {index} attempt")
            return response.text
          else:
            print(f"{index}. {expected_tag} not found...retrying")

        except:
          print("Unable to connect...Trying next proxy!")

def get_table_header(table):
    expected_titles = ['Ex-Div. Date', 'Amount', 'Type', 'Yield', 'Change', 'Decl. Date', 'Rec. Date', 'Pay. Date', 'Details']

    titles = [ column.get_text() for column in table.find_all("th")]

    msg = "Scraped titles don't match expected titles. Website table might have changed\n" \
          f"Scraped Titles: {titles}\nExpected Titles: {expected_titles}"

    if titles != expected_titles:
      raise Exception(msg)

    return titles

def get_table_rows(table):
    return [[td.get_text() for td in row.findAll("td")]
              for row in table.findAll('tr', {'class': 'LiteHover'})]

def parse_html_table(table):
    table_history = []
    titles = get_table_header(table)
    rows = get_table_rows(table)
    for row in rows:
      data = {}
      for index, title in enumerate(titles):
        data[title] = row[index]
      table_history.append(data)

    return table_history

def get_month_from_date(date):
    return date.split("/")[0]

def get_stock_payout_rate(dividend_dates):
    pay_info = { 'Annual': 1,
                 'Semi-annual': 2,
                 'Quarter': 4,
                 'Month': 12}
    type_sample = []
    for index, date in enumerate(dividend_dates):
      if index == 3:
        break
      type_sample.append(date['Type'])

    print(f"type sample found: {type_sample}")

    from collections import Counter

    occurence_count = Counter(type_sample)
    pay_type = occurence_count.most_common(1)[0][0]
    print(f"pay type most occurence was {pay_type}")

    return pay_type, pay_info[pay_type]

def get_payout_months_for_a_year(history_date_list):
    payout_months = []
    pay_type, pay_frequency = get_stock_payout_rate(history_date_list)
    print(f"\npay_type received: {pay_type} and frequency: {pay_frequency}")
    for date in history_date_list:
      month = get_month_from_date(date['Pay. Date'])
      print(f"\ncurrent month: {month} and current date: {date}")
      print(f"current payout_months: {payout_months}")
      isPayTypeCorrect = date['Type'] == pay_type
      print(f"value of isPayTypeCorrect: {isPayTypeCorrect}")
      if not isPayTypeCorrect or int(month) in payout_months:
        print(f"inside if continueing")
        continue
      elif isPayTypeCorrect and len(payout_months) == pay_frequency:
        print(f"inside else breaking")
        break

      if isPayTypeCorrect:
        print(f"adding month to payout_months")
        payout_months.append(int(month))

    return sorted(payout_months)

def write_row_to_csv_file(filename, mode, row_data):
    with open(filename, mode=mode) as csv_file:
      csv_writer = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
      csv_writer.writerow(row_data)

def isPageUpToDate(dividend_data):
    for row_date in dividend_data:
      now = datetime.datetime.now()
      if str(now.year) in row_date['Ex-Div. Date'] or str(now.year - 1) in row_date['Ex-Div. Date']:
        return True
      else:
        return False

write_row_to_csv_file(filename='stock-pay-dates.csv', mode='w', row_data=header)

with open("my-stocks.txt", "r") as file:
  for stock in file:
    stock_name = stock.strip()
    print(stock_name)
    proxy_list = get_proxies()
    proxies = cycle(proxy_list)
    proxy_pool = list(islice(proxies, len(proxy_list)))
    print(f"Number of proxies to try {len(proxy_list)}")

    url = f"https://www.streetinsider.com/dividend_history.php?q={stock_name}"

    tag = 'table'
    search_filter = {'class': 'dividends'}
    content = get_page_content(url, proxy_pool, tag, search_filter)

    current_stock = defaultdict(list)
    if content:

      soup = BeautifulSoup(content, "html.parser")
      dividend_table = soup.find(tag, **search_filter)
      dividend_dates = parse_html_table(dividend_table)
      pay_dates = get_payout_months_for_a_year(dividend_dates)
      current_stock = {"name": stock_name,
                       "pay-dates": pay_dates}

      print(current_stock)
      row_data = []
      for index, column in enumerate(header):
        dates = current_stock["pay-dates"]
        if index == 0 and isPageUpToDate(dividend_dates):
          row_data.append(current_stock["name"])
        elif index == 0 and not isPageUpToDate(dividend_dates):
          row_data.append(f"{current_stock['name']} Outdated")
        elif index in dates:
          row_data.append(current_stock["name"])
        else:
          row_data.append("")

      write_row_to_csv_file(filename='stock-pay-dates.csv', mode='a', row_data=row_data)
    else:
      print("Unable to find stock information...writing to csv file as unknown!")
      row_data = [f"{stock_name} (Check)" if index == 0 else '???' for index, column in enumerate(header)]
      write_row_to_csv_file(filename='stock-pay-dates.csv', mode='a', row_data=row_data)

