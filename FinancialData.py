from bs4 import BeautifulSoup
from urllib.request import Request, urlopen
import pandas as pd
import datetime as dt
import time, json
import matplotlib.pyplot as plt
import numpy as np
from sklearn.linear_model import LinearRegression

historical_index = pd.Series()

# 날짜 형식 반환 함수
def date_format(d=''):
	if d != '':
		this_date = pd.to_datetime(d).date()
	else:
		this_date = pd.Timestamp.today().date()
	return this_date

# 데이터 추출 함수
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
		page_n = page_n + 1
		historical_index_naver(index_cd, start_date, end_date, page_n, last_page)

	return historical_prices

# 글로벌 지수 json 크롤링 함수
def index_global(d, symbol, start_date='', end_date='', max_page=2000, pause=0.3):
	end_date = date_format(end_date)
	if start_date == '':
		start_date = end_date - pd.DateOffset(months=1)
	start_date = date_format(start_date)

	page, empty_streak = 1, 0

	# User-Agent 및 Referer 헤더 설정
	headers = {
		'User-Agent': (
			'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
			'AppleWebKit/537.36 (KHTML, like Gecko) '
			'Chrome/120.0.0.0 Safari/537.36'
		),
		'Referer': 'https://finance.naver.com/',
	}

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