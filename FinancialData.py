from bs4 import BeautifulSoup
from urllib.request import Request, urlopen
import pandas as pd
import datetime as dt
import time, json
import matplotlib.pyplot as plt
import numpy as np
from sklearn.linear_model import LinearRegression
import re

historical_index = pd.Series()

# User-Agent 및 Referer 헤더 설정
headers = {
	'User-Agent': (
		'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
		'AppleWebKit/537.36 (KHTML, like Gecko) '
		'Chrome/120.0.0.0 Safari/537.36'
	),
	'Referer': 'https://finance.naver.com/',
}

# 날짜 형식 반환 함수
def date_format(d=''):
	if d != '':
		this_date = pd.to_datetime(d).date()
	else:
		this_date = pd.Timestamp.today().date()
	return this_date

# 한국 지수 데이터 추출 함수
def historical_index_naver(index_cd, start_date='', end_date='', page_n=1, last_page=0):
	if start_date:
		start_date = date_format(start_date)
	else:
		start_date = dt.date.today()
	if end_date:
		end_date = date_format(end_date)
	else:
		end_date = dt.date.today()
	
	naver_index = 'http://finance.naver.com/sise/sise_index_day.nhn?code=' + index_cd + '&page=' + str(page_n)
	source = urlopen(naver_index).read()
	source = BeautifulSoup(source, 'lxml')

	dates = source.find_all('td', class_='date') # 날짜 수집
	prices = source.find_all('td', class_='number_1') # 지수 수집

	for n in range(len(dates)):
		if dates[n].text.split('.')[0].isdigit():
			this_date = dates[n].text
			this_date = date_format(this_date)

			if this_date <= end_date and this_date >= start_date:
				this_close = prices[n*4].text # prices 중 종가지수인 0, 4, 8...번째 데이터
				this_close = float(this_close.replace(',',''))

				historical_prices[this_date] = this_close
			elif this_date < start_date:
				return historical_prices
			

	if last_page == 0:
		last_page = source.find('td', class_='pgRR').find('a')['href'] # 마지막 페이지 주소 추출
		last_page = int(last_page.split('&')[1].split('=')[1])

	if page_n < last_page:
		historical_index_naver(index_cd, start_date, end_date, page_n + 1, last_page)

	return historical_prices

# 글로벌 지수 json 크롤링 함수
def index_global(d, symbol, start_date='', end_date='', max_page=2000, pause=0.3):
	end_date = date_format(end_date)
	if start_date == '':
		start_date = end_date - pd.DateOffset(months=1)
	start_date = date_format(start_date)

	page, empty_streak = 1, 0

	retry = 0

	while page <= max_page:
		url = 'https://finance.naver.com/world/worldDayListJson.naver?symbol=' + symbol + '&fdtc=0&page=' + str(page)
		req = Request(url, headers=headers)

		try:
			# 데이터 수신 및 파싱
			data = json.loads(urlopen(req).read().decode('euc-kr'))
		except Exception as e:
			retry += 1
			if retry > 5:
				raise RuntimeError(f'[page {page}] 5회 연속 실패: {e}')
			print(f'[page {page}] 요청 실패: {e}')
			time.sleep(5 * retry)
			continue
		retry = 0

		if not data:
			empty_streak += 1
			if empty_streak >= 3:
				print(f'[page {page}] 빈 응답 3회 연속')
				break
			time.sleep(3)
			page += 1
			continue
		empty_streak = 0
		last_date = None

		for row in data:
			this_date = pd.to_datetime(row['xymd']).date()
			last_date = this_date
			if start_date <= this_date <= end_date:
				d[this_date] = float(str(row['clos']).replace(',', ''))

		if last_date is not None and last_date < start_date:
			break

		page += 1
		time.sleep(pause)

	return d

# 종목의 상장주식 수와 유동비율 추출 함수
def stock_info(stock_cd):
	url_float = 'https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx?cmp_cd=' + stock_cd
	req = Request(url_float, headers=headers)
	source = urlopen(req).read()
	soup = BeautifulSoup(source, 'lxml')

	tmp = soup.find(id='cTB11').find_all('tr')[6].td.text.strip()
	tmp = re.split('/', tmp)

	outstanding = int(tmp[0].replace(',','').replace('주','').replace(' ',''))
	floating = float(tmp[1].replace(' ', '').replace('%',''))

	name = soup.find(id='pArea').find('div').find('div').find('tr').find('td').find('span').text

	k10_outstanding[stock_cd] = outstanding
	k10_floating[stock_cd] = floating
	k10_name[stock_cd] = name

	return

# 종목 주가 추출 함수
def historical_stock_naver(stock_cd, start_date='', end_date='', page_n=1, last_page=0):
	if start_date:
		start_date = date_format(start_date)
	else:
		start_date = dt.date.today()
	if end_date:
		end_date = date_format(end_date)
	else:
		end_date = dt.date.today()

	naver_stock = 'http://finance.naver.com/item/sise_day.nhn?code=' + stock_cd + '&page=' + str(page_n)
	req = Request(naver_stock, headers=headers)

	source = urlopen(req).read()
	source = BeautifulSoup(source, 'lxml')

	dates = source.find_all('span', class_='tah p10 gray03') # 날짜
	prices = source.find_all('td', class_='num') # 종가

	for n in range(len(dates)):
		if len(dates) > 0:
			this_date = date_format(dates[n].text)

			if this_date <= end_date and this_date >= start_date:
				this_close = float(prices[n*6].text.replace(',', ''))

				historical_prices[this_date] = this_close
			elif this_date < start_date:

				return historical_prices
			
	if last_page == 0:
		last_page = source.find_all('table')[1].find('td', class_='pgRR').find('a')['href']
		last_page = float(last_page.split('&')[1].split('=')[1])

	if page_n < last_page:
		historical_stock_naver(stock_cd, start_date, end_date, page_n + 1, last_page)

	return historical_prices

index_cd = 'KPI200'
historical_prices = dict()
kospi200 = historical_index_naver(index_cd, '2008-1-1', '2017-12-31')

index_cd = 'SPI@SPX'
historical_prices = dict()
sp500 = index_global(historical_prices, index_cd, '2008-1-1', '2017-12-31')

tmp = {'S&P500' : sp500, 'KOSPI200' : kospi200}
df = pd.DataFrame(tmp).sort_index() # 합집합 인덱스가 정렬되지 않으므로 ffill 전에 날짜순 정렬
df = df.ffill() # 직전 거래일 종가로 채움
df = df.dropna()
print(df)

fig = plt.figure(figsize=(10, 5))
ax = fig.gca()
ax.plot(df['S&P500'] / df['S&P500'].loc[dt.date(2008, 1, 2)] * 100, label='S&P500')
ax.plot(df['KOSPI200'] / df['KOSPI200'].loc[dt.date(2008, 1, 2)] * 100, label='KOSPI200')
ax.legend(loc=0)
ax.grid(True, color='0.7', linestyle=':', linewidth=1)

plt.show()

# 16년도 데이터
df_ratio_2016_now = df.loc[dt.date(2016, 1, 1):] / df.loc[dt.date(2016, 1, 4)] * 100
print(df_ratio_2016_now.head(3))

fig_2016 = plt.figure(figsize=(10, 5))
ax_2016 = fig_2016.gca()
ax_2016.plot(df_ratio_2016_now['S&P500'], label='S&P500')
ax_2016.plot(df_ratio_2016_now['KOSPI200'], label='KOSPI200')
ax_2016.legend(loc=0)
ax_2016.grid(True, color='0.7', linestyle=':', linewidth=1)

plt.show()

# 산포도
fig_scatter = plt.figure(figsize=(5, 5))
ax_scatter = fig_scatter.gca()
ax_scatter.scatter(df_ratio_2016_now['S&P500'], df_ratio_2016_now['KOSPI200'], marker='.')
ax_scatter.grid(True, color='0.7', linestyle=':', linewidth=1)
ax_scatter.set_xlabel('S&P500')
ax_scatter.set_ylabel('KOSPI200')

plt.show()

# 선형 회귀분석
x = df_ratio_2016_now['S&P500']
y = df_ratio_2016_now['KOSPI200']

independent_var = np.array(x).reshape(-1, 1)
dependent_var = np.array(y).reshape(-1, 1)

regr = LinearRegression()
regr.fit(independent_var, dependent_var)

result = {'Slope':regr.coef_[0,0], 'Intercept':regr.intercept_[0], 'R^2':regr.score(independent_var, dependent_var)}
print(result)

# 추세선
fig_linear = plt.figure(figsize=(5, 5))
ax_linear = fig_linear.gca()
ax_linear.scatter(independent_var, dependent_var, marker='.', color='skyblue')
ax_linear.plot(independent_var, regr.predict(independent_var), color='r', linewidth=3)
ax_linear.grid(True, color='0.7', linestyle=':', linewidth=1)
ax_linear.set_xlabel('S&P500')
ax_linear.set_ylabel('KOSPI200')

plt.show()

'''
한국거래소 시총 상위 10종목 (2026년8월 기준)
005930 삼성전자
000660 SK하이닉스
402340 SK스퀘어
009150 삼성전기
373220 LG에너지솔루션
005380 현대차
207940 삼성바이오로직스
105560 KB금융
032830 삼성생명
028260 삼성물산
'''
k10_component = ['005930', '000660', '402340', '009150', '373220', 
				 '005380', '207940', '105560', '032830', '028260']
k10_outstanding, k10_floating, k10_name = dict(), dict(), dict()

for stock_cd in k10_component:
	stock_info(stock_cd)
print(k10_outstanding)

k10_historical_prices = dict()

for stock_cd in k10_component:
	historical_prices = dict()
	start_date = '2025-1-1'
	end_date = '2025-12-31'
	historical_stock_naver(stock_cd, start_date, end_date)

	k10_historical_prices[stock_cd] = historical_prices

k10_historical_prices = pd.DataFrame(k10_historical_prices).sort_index()
k10_historical_prices = k10_historical_prices.ffill()
k10_historical_prices = k10_historical_prices.dropna()
print(k10_historical_prices.head(3))

tmp = {'Outstanding' : k10_outstanding,
	   'Floating' : k10_floating,
	   'Price' : k10_historical_prices.iloc[0],
	   'Name' : k10_name}
k10_info = pd.DataFrame(tmp)
k10_info['f Market Cap'] = k10_info['Outstanding'] * k10_info['Floating'] * k10_info['Price'] * 0.01
k10_info['Market Cap'] = k10_info['Outstanding']  * k10_info['Price'] * 0.01
print(k10_info.head(3))

k10_historical_mc = k10_historical_prices * k10_info['Outstanding'] * k10_info['Floating'] * 0.01
print(k10_historical_mc.head(3))
k10_historical_mc.sum(axis=1) # 일자별 시가총액 합

k10 = pd.DataFrame()
k10['K10 Market Cap'] = k10_historical_mc.sum(axis=1)
print(k10.head(3))

k10['K10'] = k10['K10 Market Cap'] / k10['K10 Market Cap'].iloc[0] * 100 # 지수화
print(k10.head(3))

# K10 지수 그래프
fig_k10 = plt.figure(figsize=(10, 5))
ax_k10 = fig_k10.gca()
ax_k10.plot(k10['K10'], label='K10')
ax_k10.legend(loc=0)
ax_k10.grid(True, color='0.7', linestyle=':', linewidth=1)

plt.show()

indices = {
	'SPI@SPX' : 'S&P 500',
	'NAS@NDX' : 'Nasdaq 100'
}

historical_indices = dict()
start_date = '2019-01-01'
end_date = '2019-03-31'
for key, value in indices.items():
	print(key, value)
	s = dict()
	s = index_global(s, key, start_date)
	historical_indices[value] = s
prices_df = pd.DataFrame(historical_indices).sort_index()

print(prices_df.tail(3))