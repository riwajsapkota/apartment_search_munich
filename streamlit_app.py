import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from urllib.parse import urljoin, quote
import json

# Configuration
MAX_PRICE = 750000
MIN_ROOMS = 3
MIN_AREA = 80
CITIES = ['München', 'Augsburg']

class RealEstateScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def scrape_immobilienscout24(self, city, max_price=MAX_PRICE, min_rooms=MIN_ROOMS, min_area=MIN_AREA):
        """Scrape ImmoScout24 for apartments"""
        apartments = []
        
        try:
            # Build search URL for ImmoScout24
            base_url = "https://www.immobilienscout24.de/Suche/de/bayern/{}/wohnung-kaufen"
            city_param = city.lower().replace('ü', 'u').replace('ä', 'a').replace('ö', 'o')
            url = base_url.format(city_param)
            
            params = {
                'price': f'-{max_price}',
                'numberofrooms': f'{min_rooms}-',
                'livingspace': f'{min_area}-',
                'pagenumber': 1
            }
            
            for page in range(1, 4):  # Scrape first 3 pages
                params['pagenumber'] = page
                response = self.session.get(url, params=params, timeout=10)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    listings = soup.find_all('div', class_='result-list-entry')
                    
                    for listing in listings:
                        try:
                            apartment = self.parse_immoscout_listing(listing, city)
                            if apartment and self.meets_criteria(apartment):
                                apartments.append(apartment)
                        except Exception as e:
                            continue
                
                time.sleep(1)  # Be respectful with requests
                
        except Exception as e:
            st.error(f"Error scraping ImmoScout24 for {city}: {str(e)}")
        
        return apartments
    
    def parse_immoscout_listing(self, listing, city):
        """Parse individual ImmoScout24 listing"""
        try:
            # Extract title
            title_elem = listing.find('h2') or listing.find('a', class_='result-list-entry__brand-title-container')
            title = title_elem.get_text(strip=True) if title_elem else "N/A"
            
            # Extract price
            price_elem = listing.find('dd', class_='grid-item') or listing.find('div', class_='result-list-entry__primary-criterion')
            price_text = price_elem.get_text(strip=True) if price_elem else "0"
            price = self.extract_number(price_text)
            
            # Extract rooms
            rooms_elem = listing.find_all('dd', class_='grid-item')
            rooms = 0
            for elem in rooms_elem:
                text = elem.get_text(strip=True)
                if 'zimmer' in text.lower() or 'zi' in text.lower():
                    rooms = self.extract_float(text)
                    break
            
            # Extract area
            area_elem = listing.find_all('dd', class_='grid-item')
            area = 0
            for elem in area_elem:
                text = elem.get_text(strip=True)
                if 'm²' in text or 'qm' in text:
                    area = self.extract_number(text)
                    break
            
            # Extract location
            location_elem = listing.find('button', class_='result-list-entry__map-link') or listing.find('div', class_='result-list-entry__address')
            location = location_elem.get_text(strip=True) if location_elem else city
            
            # Extract link
            link_elem = listing.find('a', href=True)
            link = urljoin("https://www.immobilienscout24.de", link_elem['href']) if link_elem else ""
            
            return {
                'title': title,
                'price': price,
                'rooms': rooms,
                'area': area,
                'location': location,
                'city': city,
                'link': link,
                'source': 'ImmoScout24',
                'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M')
            }
        except Exception:
            return None
    
    def scrape_immonet(self, city, max_price=MAX_PRICE, min_rooms=MIN_ROOMS, min_area=MIN_AREA):
        """Scrape Immonet for apartments"""
        apartments = []
        
        try:
            base_url = "https://www.immonet.de/immobiliensuche/sel.do"
            params = {
                'city': city,
                'marketingtype': '2',  # Kauf
                'objecttype': '1',    # Wohnung
                'pricetype': '1',
                'pricemax': max_price,
                'roomsmin': min_rooms,
                'areaMin': min_area,
                'pageoffset': 1
            }
            
            for page in range(1, 3):  # First 2 pages
                params['pageoffset'] = page
                response = self.session.get(base_url, params=params, timeout=10)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    listings = soup.find_all('div', class_='item') or soup.find_all('article', class_='item')
                    
                    for listing in listings:
                        try:
                            apartment = self.parse_immonet_listing(listing, city)
                            if apartment and self.meets_criteria(apartment):
                                apartments.append(apartment)
                        except Exception:
                            continue
                
                time.sleep(1)
                
        except Exception as e:
            st.error(f"Error scraping Immonet for {city}: {str(e)}")
        
        return apartments
    
    def parse_immonet_listing(self, listing, city):
        """Parse individual Immonet listing"""
        try:
            # Extract title
            title_elem = listing.find('h3') or listing.find('a', class_='text-225')
            title = title_elem.get_text(strip=True) if title_elem else "N/A"
            
            # Extract price
            price_elem = listing.find('div', class_='price-primary') or listing.find('strong', class_='text-250')
            price_text = price_elem.get_text(strip=True) if price_elem else "0"
            price = self.extract_number(price_text)
            
            # Extract details (rooms, area)
            details = listing.find_all('div', class_='text-100')
            rooms = 0
            area = 0
            
            for detail in details:
                text = detail.get_text(strip=True)
                if 'zimmer' in text.lower():
                    rooms = self.extract_float(text)
                elif 'm²' in text:
                    area = self.extract_number(text)
            
            # Extract location
            location_elem = listing.find('div', class_='text-100') or listing.find('p', class_='text-100')
            location = location_elem.get_text(strip=True) if location_elem else city
            
            # Extract link
            link_elem = listing.find('a', href=True)
            link = urljoin("https://www.immonet.de", link_elem['href']) if link_elem else ""
            
            return {
                'title': title,
                'price': price,
                'rooms': rooms,
                'area': area,
                'location': location,
                'city': city,
                'link': link,
                'source': 'Immonet',
                'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M')
            }
        except Exception:
            return None
    
    def scrape_ebay_kleinanzeigen(self, city, max_price=MAX_PRICE, min_rooms=MIN_ROOMS, min_area=MIN_AREA):
        """Scrape eBay Kleinanzeigen for apartments"""
        apartments = []
        
        try:
            base_url = "https://www.ebay-kleinanzeigen.de/s-wohnung-kaufen/"
            city_param = city.lower().replace(' ', '-')
            url = f"{base_url}{city_param}/c196"
            
            params = {
                'priceMax': max_price,
                'roomsMin': min_rooms,
                'areaMin': min_area
            }
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                listings = soup.find_all('article', class_='aditem') or soup.find_all('div', class_='ad-listitem')
                
                for listing in listings:
                    try:
                        apartment = self.parse_ebay_listing(listing, city)
                        if apartment and self.meets_criteria(apartment):
                            apartments.append(apartment)
                    except Exception:
                        continue
                        
        except Exception as e:
            st.error(f"Error scraping eBay Kleinanzeigen for {city}: {str(e)}")
        
        return apartments
    
    def parse_ebay_listing(self, listing, city):
        """Parse individual eBay Kleinanzeigen listing"""
        try:
            # Extract title
            title_elem = listing.find('h2') or listing.find('a', class_='ellipsis')
            title = title_elem.get_text(strip=True) if title_elem else "N/A"
            
            # Extract price
            price_elem = listing.find('strong') or listing.find('span', class_='aditem-main--middle--price-shipping--price')
            price_text = price_elem.get_text(strip=True) if price_elem else "0"
            price = self.extract_number(price_text)
            
            # Extract details from description
            description_elem = listing.find('p') or listing.find('div', class_='aditem-main--middle--description')
            description = description_elem.get_text(strip=True) if description_elem else ""
            
            rooms = self.extract_rooms_from_text(description + " " + title)
            area = self.extract_area_from_text(description + " " + title)
            
            # Extract location
            location_elem = listing.find('div', class_='aditem-main--top--left') or listing.find('span', class_='aditem-main--top--left')
            location = location_elem.get_text(strip=True) if location_elem else city
            
            # Extract link
            link_elem = listing.find('a', href=True)
            link = urljoin("https://www.ebay-kleinanzeigen.de", link_elem['href']) if link_elem else ""
            
            return {
                'title': title,
                'price': price,
                'rooms': rooms,
                'area': area,
                'location': location,
                'city': city,
                'link': link,
                'source': 'eBay Kleinanzeigen',
                'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M')
            }
        except Exception:
            return None
    
    def extract_number(self, text):
        """Extract number from text"""
        if not text:
            return 0
        numbers = re.findall(r'[\d,.]+', text.replace('.', '').replace(',', '.'))
        if numbers:
            try:
                return int(float(numbers[0].replace(',', '')))
            except:
                return 0
        return 0
    
    def extract_float(self, text):
        """Extract float number from text"""
        if not text:
            return 0
        numbers = re.findall(r'[\d,\.]+', text)
        if numbers:
            try:
                return float(numbers[0].replace(',', '.'))
            except:
                return 0
        return 0
    
    def extract_rooms_from_text(self, text):
        """Extract number of rooms from text"""
        patterns = [
            r'(\d+(?:[,\.]\d+)?)\s*(?:zimmer|zi\b)',
            r'(\d+(?:[,\.]\d+)?)\s*z\b',
            r'(\d+(?:[,\.]\d+)?)\s*room'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                return float(match.group(1).replace(',', '.'))
        return 0
    
    def extract_area_from_text(self, text):
        """Extract area from text"""
        patterns = [
            r'(\d+(?:[,\.]\d+)?)\s*(?:m²|qm|quadrat)',
            r'(\d+(?:[,\.]\d+)?)\s*m2'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                return int(float(match.group(1).replace(',', '.')))
        return 0
    
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
        default=["ImmoScout24", "Immonet", "eBay Kleinanzeigen"]
    )
    
    max_price = st.sidebar.slider("Max Price (€)", 500000, 1000000, MAX_PRICE, 10000)
    min_rooms = st.sidebar.slider("Min Rooms", 1, 6, MIN_ROOMS)
    min_area = st.sidebar.slider("Min Area (m²)", 50, 150, MIN_AREA, 5)
    
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
                    if source == "ImmoScout24":
                        apartments = scraper.scrape_immobilienscout24(city, max_price, min_rooms, min_area)
                    elif source == "Immonet":
                        apartments = scraper.scrape_immonet(city, max_price, min_rooms, min_area)
                    elif source == "eBay Kleinanzeigen":
                        apartments = scraper.scrape_ebay_kleinanzeigen(city, max_price, min_rooms, min_area)
                    else:
                        apartments = []
                    
                    all_apartments.extend(apartments)
                    
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
                        
                        if apartment['link']:
                            st.markdown(f"[View Listing]({apartment['link']})")
                    
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
            st.warning("No apartments found matching your criteria. Try adjusting your search parameters.")

if __name__ == "__main__":
    main()
