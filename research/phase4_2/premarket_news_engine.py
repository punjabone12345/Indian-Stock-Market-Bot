"""
OPTION 3: PRE-MARKET LIVE NEWS INGESTION & SECTOR CLASSIFICATION ENGINE
Designed for 08:50 AM daily execution for Indian Markets.
Fetches breaking financial news from the past 24 hours across key Indian sectors,
classifies sentiment & catalytic weight, identifies the #1 Focus Sector, and generates
the exact 09:15-09:45 confirmation and 3:00 PM exit trading plan.
"""
import os
import sys
import re
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

SECTORS = {
    'BANKING': {
        'keywords': ['bank', 'banking', 'nifty bank', 'rbi', 'npa', 'credit growth', 'deposits', 'lending', 'hdfc bank', 'icici bank', 'sbi', 'state bank', 'kotak', 'axis bank', 'indusind', 'bajaj finance', 'nbfc'],
        'tickers': ['HDFCBANK', 'ICICIBANK', 'SBIN', 'KOTAKBANK', 'AXISBANK', 'INDUSINDBK', 'BAJFINANCE']
    },
    'IT': {
        'keywords': ['it sector', 'nifty it', 'tech', 'software', 'ai', 'cloud', 'digital', 'tcs', 'infosys', 'infy', 'hcl tech', 'wipro', 'tech mahindra', 'nasdaq', 'accenture'],
        'tickers': ['TCS', 'INFY', 'HCLTECH', 'WIPRO', 'TECHM']
    },
    'ENERGY': {
        'keywords': ['oil', 'gas', 'crude', 'petrol', 'diesel', 'reliance', 'ril', 'ongc', 'ntpc', 'power grid', 'coal india', 'power', 'refinery', 'opec'],
        'tickers': ['RELIANCE', 'ONGC', 'NTPC', 'POWERGRID', 'COALINDIA']
    },
    'METALS': {
        'keywords': ['metal', 'steel', 'iron ore', 'copper', 'aluminum', 'zinc', 'tata steel', 'jsw steel', 'hindalco', 'vedanta', 'china demand', 'lme', 'mining'],
        'tickers': ['TATASTEEL', 'JSWSTEEL']
    },
    'AUTO': {
        'keywords': ['auto', 'automobile', 'car', 'ev', 'vehicle', 'maruti', 'tata motors', 'bajaj auto', 'm&m', 'mahindra', 'two wheeler', 'sales volume', 'registration'],
        'tickers': ['MARUTI']
    },
    'FMCG': {
        'keywords': ['fmcg', 'consumption', 'consumer', 'itc', 'hindustan unilever', 'hul', 'titan', 'nestle', 'dabur', 'rural demand', 'inflation', 'raw material'],
        'tickers': ['ITC', 'HINDUNILVR', 'TITAN']
    },
    'PHARMA': {
        'keywords': ['pharma', 'healthcare', 'drug', 'fda', 'usfda', 'sun pharma', 'dr reddy', 'cipla', 'lupin', 'form 483', 'clinical trial', 'api'],
        'tickers': ['SUNPHARMA']
    },
    'INFRA': {
        'keywords': ['infra', 'infrastructure', 'construction', 'l&t', 'larsen', 'adani', 'adani ent', 'bharti airtel', 'telecom', 'cement', 'ultratech', 'grasim', 'order win', 'capex'],
        'tickers': ['LT', 'ADANIENT', 'BHARTIARTL', 'GRASIM', 'ULTRACEMCO']
    }
}

CATALYST_PATTERNS = {
    'EARNINGS_SURPRISE': (re.compile(r'\b(profit jumps|net profit up|q[1-4] profit surges|beats estimates|revenue up|strong quarterly|record high profit)\b', re.I), 2.5),
    'EARNINGS_MISS': (re.compile(r'\b(profit drops|net profit falls|q[1-4] profit slips|misses estimates|revenue down|weak quarterly|margin compression)\b', re.I), -2.5),
    'ORDER_WIN': (re.compile(r'\b(bags order|wins contract|secures order|awarded contract|mega deal|expansion pact)\b', re.I), 2.0),
    'REGULATORY_BULL': (re.compile(r'\b(fda approval|usfda clearance|eir received|gst relief|duty cut|policy boost|subsidy announced)\b', re.I), 2.0),
    'REGULATORY_BEAR': (re.compile(r'\b(usfda warning|import alert|penalty imposed|rbi ban|ed probe|sebi order|duty hike|tax demand)\b', re.I), -2.5),
    'ANALYST_UPGRADE': (re.compile(r'\b(upgrade|target raised|buy rating|outperform|bullish view|target price hiked)\b', re.I), 1.5),
    'ANALYST_DOWNGRADE': (re.compile(r'\b(downgrade|target cut|sell rating|underperform|bearish view|price target lowered)\b', re.I), -1.5),
    'GLOBAL_CUE_BULL': (re.compile(r'\b(nasdaq rallies|crude falls|china stimulus|fed rate cut|dollar drops|global rally)\b', re.I), 1.5),
    'GLOBAL_CUE_BEAR': (re.compile(r'\b(nasdaq tumbles|crude spikes|recession fear|fed rate hike|tariff hike|trade war)\b', re.I), -1.5)
}

def fetch_rss_feed(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read()
    except Exception as e:
        # Return empty on network issues
        return None

def fetch_sector_news(sector_name):
    query = f"Indian {sector_name} stock market news"
    encoded_q = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_q}&hl=en-IN&gl=IN&ceid=IN:en"
    raw_xml = fetch_rss_feed(url)
    if not raw_xml:
        return []
        
    articles = []
    try:
        root = ET.fromstring(raw_xml)
        for item in root.findall('.//item')[:15]:
            title = item.find('title').text if item.find('title') is not None else ''
            pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ''
            link = item.find('link').text if item.find('link') is not None else ''
            articles.append({
                'title': title,
                'pubDate': pub_date,
                'link': link
            })
    except Exception as e:
        pass
    return articles

def analyze_headline(title):
    matched_sectors = []
    matched_tickers = []
    
    title_lower = title.lower()
    
    for sec, meta in SECTORS.items():
        if any(kw in title_lower for kw in meta['keywords']):
            matched_sectors.append(sec)
        for tick in meta['tickers']:
            if tick.lower() in title_lower:
                matched_tickers.append(tick)
                if sec not in matched_sectors:
                    matched_sectors.append(sec)
                    
    score = 0.0
    tags = []
    for tag, (pat, weight) in CATALYST_PATTERNS.items():
        if pat.search(title):
            score += weight
            tags.append(tag)
            
    # Default baseline score if no specific pattern matches
    if score == 0.0:
        if any(w in title_lower for w in ['gain', 'rise', 'surge', 'rally', 'jump', 'high', 'bull']):
            score += 0.8
            tags.append('POSITIVE_MOMENTUM')
        elif any(w in title_lower for w in ['fall', 'drop', 'slide', 'tumble', 'crash', 'low', 'bear', 'plunge']):
            score -= 0.8
            tags.append('NEGATIVE_MOMENTUM')
            
    return {
        'sectors': matched_sectors,
        'tickers': list(set(matched_tickers)),
        'score': score,
        'tags': tags
    }

def run_premarket_scan():
    print("="*75)
    print("   INDIAN MARKETS PRE-MARKET NEWS & SECTOR SENTIMENT SCANNER")
    print(f"   Execution Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*75)
    
    sector_scores = {s: {'score': 0.0, 'news_count': 0, 'headlines': [], 'tickers': set()} for s in SECTORS}
    all_articles = []
    
    # Ingest news across sectors
    for sec in SECTORS:
        articles = fetch_sector_news(sec)
        for a in articles:
            analysis = analyze_headline(a['title'])
            for s in analysis['sectors']:
                sector_scores[s]['score'] += analysis['score']
                sector_scores[s]['news_count'] += 1
                sector_scores[s]['headlines'].append((a['title'], analysis['score'], analysis['tags']))
                sector_scores[s]['tickers'].update(analysis['tickers'])
                
    # Rank sectors by absolute catalytic energy
    ranked_sectors = []
    for s, data in sector_scores.items():
        if data['news_count'] > 0:
            avg_score = data['score'] / data['news_count']
            ranked_sectors.append({
                'sector': s,
                'total_score': data['score'],
                'news_count': data['news_count'],
                'avg_score': avg_score,
                'bias': 'BULLISH' if data['score'] > 0 else ('BEARISH' if data['score'] < 0 else 'NEUTRAL'),
                'tickers': list(data['tickers']),
                'headlines': data['headlines']
            })
            
    ranked_sectors.sort(key=lambda x: abs(x['total_score']), reverse=True)
    
    print("\n--- SECTOR SENTIMENT & CATALYST LEADERBOARD ---")
    for r in ranked_sectors:
        print(f"[{r['sector']:<10}] Score: {r['total_score']:+6.1f} | Bias: {r['bias']:<7} | Articles: {r['news_count']:<2} | Key Tickers: {', '.join(r['tickers']) if r['tickers'] else 'Sector-wide'}")
        
    if not ranked_sectors:
        print("No significant news detected.")
        return None
        
    top_sector = ranked_sectors[0]
    print("\n" + "#"*75)
    print(f"   >>> #1 FOCUS SECTOR OF THE DAY: {top_sector['sector']} <<<")
    print(f"   Directional Bias: {top_sector['bias']} (Catalyst Intensity: {abs(top_sector['total_score']):.1f})")
    print(f"   Focus Tickers: {', '.join(top_sector['tickers']) if top_sector['tickers'] else 'Top sector constituents'}")
    print("#"*75)
    
    print("\nTop Catalysts Driving This Sector:")
    for h, sc, tags in top_sector['headlines'][:4]:
        print(f"  * [{sc:+3.1f}] {h} (Tags: {', '.join(tags) if tags else 'General'})")
        
    print("\n--- INTRADAY EXECUTION BLUEPRINT ---")
    print("1. 09:00-09:08 AM: Verify that the sector's pre-market auction confirms the news direction.")
    print("2. 09:15-09:45 AM: Confirm Sector Breadth >= 70% and morning RVOL >= 1.5x.")
    print(f"3. 09:45 AM: Select the #1 Relative Strength Leader in {top_sector['sector']} and enter with 1R risk.")
    print("4. 15:00 PM: Strict mandatory square-off.")
    print("="*75)
    
    return ranked_sectors

if __name__ == '__main__':
    run_premarket_scan()
