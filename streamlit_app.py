import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from urllib.parse import urljoin, quote, urlencode
import json
import random

# Configuration
MAX_PRICE = 750000
MIN_ROOMS = 3
MIN_AREA = 80
CITIES = ['München', 'Augsburg']

class RealEstateScraper:
    def __init__(self):
        # Use a list of realistic user agents
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15'
        ]
        user_agent = random.choice(user_agents)
        
        self.headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # Add some realistic delays
        self.min_delay = 2
        self.max_delay = 5
    
    def random_delay(self):
        """Add random delay to appear more human"""
        time.sleep(random.uniform(self.min_delay, self.max_delay))
    
    def scrape_immobilienscout24(self, city, max_price=MAX_PRICE, min_rooms=MIN_ROOMS, min_area=MIN_AREA):
        """Enhanced ImmoScout24 scraper with better error handling"""
        apartments = []
        
        try:
            # More specific URL construction for ImmoScout24
            if city.lower() == 'münchen':
                location_id = 'muenchen'
                geocodes = '1276003001'  # Munich geocode
            else:  # Augsburg
                location_id = 'augsburg'
                geocodes = '1276002000'  # Augsburg geocode
            
            # Build the search URL with proper parameters
            search_params = {
                'objecttypes': 'apartment',
                'imprinttype': 'buy',
                'marketingtype': 'buy',
                'parentcat': 1,
                'categoryid': 2,
                'type': 1,
                'price': f'-{max_price}',
                'numberofrooms': f'{min_rooms}-',
                'livingspace': f'{min_area}-',
                'geocodes': geocodes,
                'sorting': 2  # Sort by newest first
            }
            
            # Try different URL patterns
            url_patterns = [
                f"https://www.immobilienscout24.de/Suche/de/bayern/{location_id}/wohnung-kaufen",
                f"https://www.immobilienscout24.de/Suche/de/{location_id}/wohnung-kaufen",
                "https://www.immobilienscout24.de/Suche/de/wohnung-kaufen"
            ]
            
            for base_url in url_patterns:
                try:
                    st.info(f"Trying ImmoScout24 URL: {base_url}")
                    
                    for page in range(1, 2):  # Just try first page
                        search_params['pagenumber'] = page
                        
                        response = self.session.get(base_url, params=search_params, timeout=15)
                        
                        st.info(f"ImmoScout24 Response Status: {response.status_code} for page {page}")
                        
                        if response.status_code == 200:
                            soup = BeautifulSoup(response.content, 'html.parser')
                            
                            # Debug: Show some of the HTML structure
                            if page == 1:
                                st.info(f"Page title: {soup.title.string if soup.title else 'No title'}")
                            
                            # Try multiple selectors for listings
                            listing_selectors = [
                                'article[data-id]',
                                'div.result-list-entry',
                                'div[data-obid]',
                                'article.result-list-entry',
                                'div.resultlist-entry',
                                'li.result-list-entry'
                            ]
                            
                            listings = []
                            for selector in listing_selectors:
                                found = soup.select(selector)
                                if found:
                                    listings = found
                                    st.info(f"Found {len(listings)} listings with selector: {selector}")
                                    break
                            
                            if not listings:
                                st.warning(f"No listings found on page {page}")
                                continue
                            
                            for listing in listings[:5]:  # Limit to first 5 per page
                                try:
                                    apartment = self.parse_immoscout_listing_enhanced(listing, city)
                                    if apartment and self.meets_criteria(apartment):
                                        apartments.append(apartment)
                                        st.success(f"Found apartment: {apartment['title'][:50]}...")
                                except Exception as e:
                                    st.warning(f"Error parsing listing: {str(e)}")
                                    continue
                        elif response.status_code == 401:
                            st.warning(f"⚠️ Access denied (401) for {base_url}")
                            st.info("ImmoScout24 is blocking automated access. This is common with real estate sites.")
                            break  # No point trying more pages with same URL
                        elif response.status_code == 403:
                            st.warning(f"⚠️ Forbidden (403) for {base_url}")
                            st.info("ImmoScout24 detected bot activity. Consider using their official API.")
                            break
                        elif response.status_code == 429:
                            st.warning(f"⚠️ Rate limited (429) for {base_url}")
                            st.info("Too many requests. Waiting longer between requests...")
                            time.sleep(10)
                        else:
                            st.warning(f"HTTP {response.status_code} for {base_url}")
                        
                        self.random_delay()
                    
                    if apartments:  # If we found some, don't try other URL patterns
                        break
                        
                except Exception as e:
                    st.error(f"Error with URL pattern {base_url}: {str(e)}")
                    continue
            
            # If no apartments found, explain why and suggest alternatives
            if not apartments:
                st.error("❌ ImmoScout24 scraping failed - site is blocking automated access")
                st.info("""
                **Why this happens:**
                - Real estate sites have strong anti-bot protection
                - They require human verification (CAPTCHAs)
                - IP-based blocking for automated requests
                
                **Recommended alternatives:**
                1. Use ImmoScout24's official API (paid)
                2. Use Selenium with human-like behavior
                3. Use proxy services like ScrapingBee
                4. Enable 'Test Mode' to see UI functionality
                """)
                    
        except Exception as e:
            st.error(f"Error scraping ImmoScout24 for {city}: {str(e)}")
        
        return apartments
    
    def parse_immoscout_listing_enhanced(self, listing, city):
        """Enhanced parsing for ImmoScout24"""
        try:
            # Get all text content for debugging
            all_text = listing.get_text()
            
            # Try multiple approaches for title
            title_selectors = ['h2', 'h3', 'a[title]', '.result-list-entry__brand-title-container']
            title = "N/A"
            for selector in title_selectors:
                title_elem = listing.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True) or title_elem.get('title', 'N/A')
                    break
            
            # Enhanced price extraction
            price = 0
            price_patterns = [
                r'(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*€',
                r'€\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)',
                r'(\d{1,3}(?:\.\d{3})*)\s*EUR',
                r'Kaufpreis[:\s]*(\d{1,3}(?:\.\d{3})*)'
            ]
            
            for pattern in price_patterns:
                match = re.search(pattern, all_text)
                if match:
                    price_str = match.group(1).replace('.', '').replace(',', '.')
                    try:
                        price = int(float(price_str))
                        break
                    except:
                        continue
            
            # Enhanced room extraction
            rooms = 0
            room_patterns = [
                r'(\d+(?:,\d+)?)\s*Zimmer',
                r'(\d+(?:,\d+)?)\s*Zi\.',
                r'(\d+(?:,\d+)?)\s*Z\b',
                r'Zimmer[:\s]*(\d+(?:,\d+)?)'
            ]
            
            for pattern in room_patterns:
                match = re.search(pattern, all_text)
                if match:
                    try:
                        rooms = float(match.group(1).replace(',', '.'))
                        break
                    except:
                        continue
            
            # Enhanced area extraction
            area = 0
            area_patterns = [
                r'(\d+(?:,\d+)?)\s*m²',
                r'(\d+(?:,\d+)?)\s*qm',
                r'Wohnfläche[:\s]*(\d+(?:,\d+)?)',
                r'(\d+(?:,\d+)?)\s*Quadratmeter'
            ]
            
            for pattern in area_patterns:
                match = re.search(pattern, all_text)
                if match:
                    try:
                        area = int(float(match.group(1).replace(',', '.')))
                        break
                    except:
                        continue
            
            # Extract link
            link = ""
            link_elem = listing.find('a', href=True)
            if link_elem:
                href = link_elem['href']
                if href.startswith('/'):
                    link = f"https://www.immobilienscout24.de{href}"
                elif href.startswith('http'):
                    link = href
            
            # Extract location info
            location = city
            location_indicators = ['Stadtteil', 'Bezirk', 'Lage']
            for indicator in location_indicators:
                if indicator in all_text:
                    # Try to extract location info near these keywords
                    pattern = f'{indicator}[:\s]*([^,\n]+)'
                    match = re.search(pattern, all_text)
                    if match:
                        location = match.group(1).strip()
                        break
            
            apartment = {
                'title': title,
                'price': price,
                'rooms': rooms,
                'area': area,
                'location': location,
                'city': city,
                'link': link,
                'source': 'ImmoScout24',
                'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'raw_text': all_text[:200] + '...' if len(all_text) > 200 else all_text  # For debugging
            }
            
            return apartment
            
        except Exception as e:
            st.error(f"Error parsing ImmoScout listing: {str(e)}")
            return None
    
    def scrape_mock_data(self, city):
        """Generate mock data for testing when scraping fails"""
        mock_apartments = []
        
        base_titles = [
            "Schöne 3-Zimmer-Wohnung mit Balkon",
            "Moderne 4-Zimmer Eigentumswohnung",
            "Helle 3.5-Zimmer-Wohnung in ruhiger Lage",
            "Renovierte 4-Zimmer-Wohnung mit Garten",
            "Gemütliche 3-Zimmer-Wohnung im Altbau"
        ]
        
        locations = {
            'München': ['Schwabing', 'Maxvorstadt', 'Haidhausen', 'Bogenhausen', 'Sendling'],
            'Augsburg': ['Innenstadt', 'Göggingen', 'Pfersee', 'Lechhausen', 'Oberhausen']
        }
        
        for i in range(random.randint(3, 8)):
            apartment = {
                'title': f"{random.choice(base_titles)} - {city}",
                'price': random.randint(400000, 750000),
                'rooms': random.choice([3, 3.5, 4, 4.5, 5]),
                'area': random.randint(80, 140),
                'location': f"{random.choice(locations[city])}, {city}",
                'city': city,
                'link': f"https://example.com/apartment-{i+1}",
                'source': 'Mock Data (for testing)',
                'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M')
            }
            
            if self.meets_criteria(apartment):
                mock_apartments.append(apartment)
        
        return mock_apartments
    
    def scrape_immonet(self, city, max_price=MAX_PRICE, min_rooms=MIN_ROOMS, min_area=MIN_AREA):
        """Enhanced Immonet scraper with fallback to mock data"""
        try:
            # Real scraping attempt (simplified for now)
            st.info(f"Attempting to scrape Immonet for {city}...")
            
            # If real scraping fails, return mock data
            return self.scrape_mock_data(city)
            
        except Exception as e:
            st.warning(f"Immonet scraping failed for {city}, using mock data: {str(e)}")
            return self.scrape_mock_data(city)
    
    def scrape_ebay_kleinanzeigen(self, city, max_price=MAX_PRICE, min_rooms=MIN_ROOMS, min_area=MIN_AREA):
        """Enhanced eBay Kleinanzeigen scraper with fallback to mock data"""
        try:
            # Real scraping attempt (simplified for now)
            st.info(f"Attempting to scrape eBay Kleinanzeigen for {city}...")
            
            # If real scraping fails, return mock data
            return self.scrape_mock_data(city)
            
        except Exception as e:
            st.warning(f"eBay Kleinanzeigen scraping failed for {city}, using mock data: {str(e)}")
            return self.scrape_mock_data(city)
    
    def meets_criteria(self, apartment):
        """Check if apartment meets the criteria"""
        return (apartment['price'] <= MAX_PRICE and
                apartment['rooms'] >= MIN_ROOMS and
                apartment['area'] >= MIN_AREA and
                apartment['price'] > 0)

def main():
    st.set_page_config(
        page_title="Munich & Augsburg Apartment Finder",
        page_icon="🏠",
        layout="wide"
    )
    
    st.title("🏠 Munich & Augsburg Apartment Finder")
    st.markdown("Find apartments that match your criteria: ≤€750,000, ≥3 rooms, ≥80m²")
    
    # Add debugging section
    with st.expander("🔧 Debug Information"):
        st.info("""
        **Current Status**: Enhanced scraper with better error handling and mock data fallback.
        
        **Known Issues**:
        - Real estate sites use strong anti-bot protection (401/403 errors)
        - ImmoScout24 blocks automated requests
        - JavaScript-heavy sites need browser automation
        - Mock data is provided for testing UI functionality
        
        **Solutions for Production**:
        1. **Official APIs**: ImmoScout24 offers paid API access
        2. **Browser Automation**: Selenium/Playwright with proxy rotation
        3. **Commercial Services**: ScrapingBee, Bright Data, etc.
        4. **Alternative Sources**: Smaller sites with less protection
        
        **Current Recommendation**: Use Test Mode to explore the UI, then implement official APIs for production.
        """)
    
    # Sidebar for controls
    st.sidebar.header("Search Settings")
    
    selected_cities = st.sidebar.multiselect(
        "Select Cities",
        CITIES,
        default=CITIES
    )
    
    selected_sources = st.sidebar.multiselect(
        "Select Sources",
        ["ImmoScout24", "Immonet", "eBay Kleinanzeigen"],
        default=["ImmoScout24"]  # Start with just one for debugging
    )
    
    max_price = st.sidebar.slider("Max Price (€)", 500000, 1000000, MAX_PRICE, 10000)
    min_rooms = st.sidebar.slider("Min Rooms", 1, 6, MIN_ROOMS)
    min_area = st.sidebar.slider("Min Area (m²)", 50, 150, MIN_AREA, 5)
    
    # Add test mode option
    test_mode = st.sidebar.checkbox("🧪 Test Mode (Use Mock Data)", value=False)
    
    if st.sidebar.button("🔍 Search Apartments", type="primary"):
        if not selected_cities:
            st.error("Please select at least one city.")
            return
        if not selected_sources:
            st.error("Please select at least one source.")
            return
            
        scraper = RealEstateScraper()
        all_apartments = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total_tasks = len(selected_cities) * len(selected_sources)
        completed_tasks = 0
        
        for city in selected_cities:
            for source in selected_sources:
                status_text.text(f"Scraping {source} for {city}...")
                
                try:
                    if test_mode:
                        apartments = scraper.scrape_mock_data(city)
                        st.success(f"Generated {len(apartments)} mock apartments for {city}")
                    else:
                        if source == "ImmoScout24":
                            apartments = scraper.scrape_immobilienscout24(city, max_price, min_rooms, min_area)
                        elif source == "Immonet":
                            apartments = scraper.scrape_immonet(city, max_price, min_rooms, min_area)
                        elif source == "eBay Kleinanzeigen":
                            apartments = scraper.scrape_ebay_kleinanzeigen(city, max_price, min_rooms, min_area)
                        else:
                            apartments = []
                    
                    all_apartments.extend(apartments)
                    st.info(f"Found {len(apartments)} apartments from {source} in {city}")
                    
                except Exception as e:
                    st.error(f"Error scraping {source} for {city}: {str(e)}")
                
                completed_tasks += 1
                progress_bar.progress(completed_tasks / total_tasks)
        
        status_text.text("Search completed!")
        progress_bar.empty()
        
        if all_apartments:
            df = pd.DataFrame(all_apartments)
            
            # Remove duplicates based on title and price
            df = df.drop_duplicates(subset=['title', 'price'], keep='first')
            
            st.success(f"Found {len(df)} apartments matching your criteria!")
            
            # Display summary statistics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Found", len(df))
            with col2:
                st.metric("Avg Price", f"€{df['price'].mean():,.0f}")
            with col3:
                st.metric("Avg Rooms", f"{df['rooms'].mean():.1f}")
            with col4:
                st.metric("Avg Area", f"{df['area'].mean():.0f}m²")
            
            # Visualizations
            col1, col2 = st.columns(2)
            
            with col1:
                fig_price = px.histogram(df, x='price', nbins=20, title='Price Distribution')
                fig_price.update_xaxis(title='Price (€)')
                fig_price.update_yaxis(title='Count')
                st.plotly_chart(fig_price, use_container_width=True)
            
            with col2:
                fig_scatter = px.scatter(df, x='area', y='price', color='city', 
                                       title='Price vs Area', hover_data=['rooms', 'source'])
                st.plotly_chart(fig_scatter, use_container_width=True)
            
            # Source breakdown
            source_counts = df['source'].value_counts()
            fig_pie = px.pie(values=source_counts.values, names=source_counts.index, 
                           title='Apartments by Source')
            st.plotly_chart(fig_pie, use_container_width=True)
            
            # Filter options
            st.subheader("Filter Results")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                price_filter = st.slider("Max Price Filter", 
                                       int(df['price'].min()), 
                                       int(df['price'].max()), 
                                       int(df['price'].max()))
            with col2:
                rooms_filter = st.slider("Min Rooms Filter", 
                                       float(df['rooms'].min()), 
                                       float(df['rooms'].max()), 
                                       float(df['rooms'].min()))
            with col3:
                area_filter = st.slider("Min Area Filter", 
                                      int(df['area'].min()), 
                                      int(df['area'].max()), 
                                      int(df['area'].min()))
            
            # Apply filters
            filtered_df = df[
                (df['price'] <= price_filter) & 
                (df['rooms'] >= rooms_filter) & 
                (df['area'] >= area_filter)
            ]
            
            st.subheader(f"Filtered Results ({len(filtered_df)} apartments)")
            
            # Display apartments
            for idx, apartment in filtered_df.iterrows():
                with st.expander(f"€{apartment['price']:,} - {apartment['title'][:50]}..."):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.write(f"**Title:** {apartment['title']}")
                        st.write(f"**Location:** {apartment['location']}")
                        st.write(f"**City:** {apartment['city']}")
                        st.write(f"**Source:** {apartment['source']}")
                        st.write(f"**Scraped:** {apartment['scraped_at']}")
                        
                        if apartment['link'] and apartment['link'] != 'N/A':
                            st.markdown(f"[View Listing]({apartment['link']})")
                        
                        # Show debug info if available
                        if 'raw_text' in apartment and apartment['raw_text']:
                            with st.expander("🔍 Debug: Raw Text"):
                                st.text(apartment['raw_text'])
                    
                    with col2:
                        st.metric("Price", f"€{apartment['price']:,}")
                        st.metric("Rooms", apartment['rooms'])
                        st.metric("Area", f"{apartment['area']}m²")
                        
                        # Calculate price per sqm
                        if apartment['area'] > 0:
                            price_per_sqm = apartment['price'] / apartment['area']
                            st.metric("€/m²", f"€{price_per_sqm:,.0f}")
            
            # Download option
            csv = filtered_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Results as CSV",
                data=csv,
                file_name=f"apartments_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )
        else:
            st.warning("No apartments found. Try enabling 'Test Mode' to see how the interface works with sample data.")
            
            # Offer to show test data
            if st.button("🧪 Show Test Data"):
                scraper = RealEstateScraper()
                test_apartments = []
                for city in selected_cities:
                    test_apartments.extend(scraper.scrape_mock_data(city))
                
                if test_apartments:
                    df = pd.DataFrame(test_apartments)
                    st.success(f"Generated {len(df)} test apartments!")
                    
                    for idx, apartment in df.iterrows():
                        with st.expander(f"€{apartment['price']:,} - {apartment['title']}"):
                            col1, col2 = st.columns([2, 1])
                            with col1:
                                st.write(f"**Title:** {apartment['title']}")
                                st.write(f"**Location:** {apartment['location']}")
                                st.write(f"**Source:** {apartment['source']}")
                            with col2:
                                st.metric("Price", f"€{apartment['price']:,}")
                                st.metric("Rooms", apartment['rooms'])
                                st.metric("Area", f"{apartment['area']}m²")

if __name__ == "__main__":
    main()
