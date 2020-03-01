from requests import get
from requests.exceptions import RequestException
from contextlib import closing
from bs4 import BeautifulSoup, FeatureNotFound
from settings import *
import logging
from exceptions import *
import ast
import re


"""
**************************************************************************************************************
Second version of scraper.
Things that have been changed:
- this version provides more control of how many products/stores are scrapped. It was implemented,
 because some products are available in many stores and in most cases we do not want to scrap all this offers
(lower the offers on the list, price is higher)
- to provide simplicity and control of using above extension, new class has been created (DetailedSite), 
that represents page of stores that offer one product (e.g. https://www.skapiec.pl/site/cat/200/comp/866987400)
- method scrap_product() is deprecated, now the same (or similar) application might be achieved by
 calling load_product_store(num), and then call scrap_nstores(n) on the object returned by previous method
- some methods have been divided into smaller parts in order to provide accurate exception handling 
- more logs have been added 

Author: Jakobczak Dawid 
Feel free to ask if you have any questions.
**************************************************************************************************************
How to use it?
- firstly you have to create an object of SkapiecScraper class
- call method load_page(<product_name>) on an instance of SkapiecScraper
- if page was loaded successfully then you can call load_product_stores to get DetailedSite object
- DetailedSite provides all necessary methods to scrap products (see documentation below)


Why it does not work ?
sudo pip install lxml
sudo pip install bs4 / pip install beautifulsoup4
and maybe other modules... 
**************************************************************************************************************
"""

# file logs
# logging.basicConfig(filename=LOGGING_FILE, format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
# console logs
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

ID_COUNTER = 1

def get_request(url):
    """
    Simple http get method, if error occurs it returns None
    :param url:
    :return:    (bytes)   : raw html content of the requested site
    """
    try:
        with closing(get(url, stream=True)) as resp:
            if is_good_response(resp):
                return resp.content
            else:
                return None

    except RequestException as e:
        log_error(f'[get request] Error during requests to {url} : {str(e)}')
        return None


def is_good_response(resp):
    """
    Returns True if the response seems to be HTML, False otherwise.
    """
    content_type = resp.headers['Content-Type'].lower()
    return (resp.status_code == 200
            and content_type is not None
            and content_type.find('html') > -1)


def log_error(e):
    logging.error(str(e))


class DetailedSite:
    """
    This class is a representation of a site which contains a list of stores that sell one product.
    Main goal is to scrap all necessary information about different stores that offer the product.
    Due to possibility of choosing number of stores to be scrapped you can control how many http requests you want to make.
    """

    def __init__(self, url, pid):
        """
        :param url:     (str)   : url of skapiec page with stores from which we can buy product
        """
        self.url = url
        self.page = ""
        self.stores_boxes = []
        self.pid = pid

        self.get_page()
        self.extract_stores()

    def get_page(self):
        self.page = get_request(self.url)

    def extract_stores(self):
        """
        Finds all html contents that contain all information about offer.
        Saves it in class variable self.stores_boxes.
        :return:
        """
        try:
            soup = BeautifulSoup(self.page, 'lxml')
            # self.full_name = soup.find('div', class_='header-content').h1.text
            self.stores_boxes = soup.find_all('a', class_=PRODUCT_CLASS_D)
            logging.info('[extract_stores] found %s store(s)', len(self.stores_boxes))
        except Exception as e:
            logging.error('[extract_stores] error while parsing page: {}'.format(str(e)))

    def scrap_all_stores(self):
        """
        Scraps all previously extracted stores and returns list of scrapped products.
        :return:    (List<Product>) : list of scrapped products
        """
        products = []
        for k in range(len(self.stores_boxes)):
            p = self.scrap_store(k)
            if p:
                products.append(p)
        return products

    def scrap_nstores(self, n, start=0):
        """
        Scrap N stores by starting from [start] index in self.stores_boxes.
        If start+N exceeds length of self.stores_boxes, result will be cut.
        If start exceeds length of self.stores_boxes, empty list will be returned.
        :param start:   (int)           : start index of self.stores_boxes
        :param n:       (int)           : amount of stores to be scrapped
        :return:        (List<Product>) : list of scrapped products
        """
        products = []
        end = start + n
        end = min(len(self.stores_boxes), end)

        for k in range(start, end):
            p = self.scrap_store(k)
            if p:
                products.append(p)
        logging.info(f'[scrap_nstores] returned {len(products)} products')
        return products

    def scrap_store(self, num):
        """
        Scraps all necessary information about product's offer from one store.
        :param num:     (int)       : index of store which information will be scrapped
        :return:        (Product)   : scrapped product, None if delivery is not specified
        """
        if -1 < num < len(self.stores_boxes):
            pbox = self.stores_boxes[num]
        else:
            logging.error('[scrap_store]: {num} is greater than self.stores_boxes length')
            return None
        try:
            # firstly check deliveries, if there no information about delivery price - skip that product
            delivery_prices = self.get_deliveries(pbox)
            if not delivery_prices:
                logging.info('[scrap_store] delivery is not specified')
                return None

            href = pbox['href']
            name = pbox.find('span', class_='description gtm_or_name').text
            shop_link = URL + href
            store_name = self.get_store_name(pbox)
            rating_avg, rating_count = self.get_rating(pbox)

            base_price = float(
                pbox.find('span', class_="price gtm_or_price").text.replace("zł", "").replace(",", ".").replace(" ", ""))

            return Product(self.pid, name[:60], base_price, delivery_prices, rating_avg, rating_count, shop_link, store_name)
        except Exception as e:
            logging.error('[scrap store] error while scrapping store: {}'.format(str(e)))

    def get_deliveries(self, box):
        """
        Finds html tag that holds information about deliveries, if delivery is free then returns one-element list,
         otherwise calls proper method to scrap all delivery possibilities.
        :param box:     (str)   : html content that contains information about order
        :return:        (List)  : list of delivery prices
        """
        if box.find('span', class_="delivery-cost free-delivery badge gtm_bdg_fd"):  # free delivery
            delivery_prices = [0.00]
        else:
            delivery_url = box.find('a', class_="delivery-cost link gtm_oa_shipping")['href']
            delivery_prices = self.get_delivery_price(delivery_url)
        return delivery_prices

    def get_store_name(self, box):
        """
        Extracts name of the store from html content.
        :param box: (str)   : html content that should contains information about store name
        :return:    (str)   : store name
        """
        shop_name_tag = box.find('img', class_='offer-dealer-logo gtm_bdg_l')
        if not shop_name_tag:
            shop_name = box.find('b', class_='offer-dealer-logo').text.strip()

        else:
            shop_name = shop_name_tag['alt']
        return shop_name

    def get_rating(self, box):
        """
        Extracts number of rates and average rate of the store
        :param box:
        :return:    (tuple) : rating average (float), number of rates (int)
        """
        rating_avg = 0
        rating_count = 0

        div_rating = box.find('div', class_="shop-rating gtm_stars")

        # some stores do not have rating
        if div_rating:
            rating_descr = div_rating['data-description']
            rating_dict = ast.literal_eval(rating_descr)        # string structure to python dictionary
            rating_avg = rating_dict['avg']
            rating_count = rating_dict['count']

        return rating_avg, rating_count

    # do not look through every page when there is no information about delivery (check that!)
    def get_delivery_price(self, delivery_url):  # iterate through delivery options url 1-5
        """
        Gets all the possible delivery costs. If prices are not specified, returns empty list.
        If delivery is free 0.00 price is added to the returned list.
        :param delivery_url:    (str)           : url of delivery details site
        :return:                (list<float>)   : list of all the delivery prices
        """
        prices_list = []

        for k in range(1, DELIVERY_METHODS + 1):
            if k == 3 or k == 4:          # personal pickup - ignore that case
                continue
            d_url = delivery_url + f"&t={k}"
            d_url = URL + d_url
            page = get_request(d_url)
            if page:
                soup = BeautifulSoup(page, 'lxml')
                if not soup.find('div', id="product_content"):          # no delivery information at all
                    break

                prices = soup.find('table', id='deliveryRulesets')      # find table with all the prices
                if not prices:
                    logging.error('no delivery options')
                    continue

                for b in prices.find_all('b'):
                    price = b.text.strip()
                    pattern = r"od.*\s*.*do"
                    if re.match(pattern, price):        # price might be ~ "od x zł do y zł"
                        p = re.compile(r"od\s+(\d+\.\d+).*\s*do")   # pattern for minimum price
                        price = p.search(price).group(1)
                        prices_list.append(float(price))
                    else:
                        prices_list.append(float(b.text.replace('zł', '').strip()))
            else:
                logging.info('[get_delivery_prices]: no page returned, url={}'.format(d_url))
        return prices_list


class SkapiecScraper:
    """
    Handles all scraping things. Due to technical restrictions class is limited to scrap first 7 or 8 products.
    This restriction is caused by architecture of skapiec.pl site. Site is loaded partially -
    it uses javascript to lazy load more products after scroll event is triggered on the site.
    """

    def __init__(self, pid=0):
        self.base_url = URL
        self.products_boxes = []
        self.products_overview = []
        self.pid = pid

    def load_page(self, product_name):
        """
        Loads page and saves its html.
        :param product_name:    (str)   : name of desired product
        :return:                (bool)  : True if the page is loaded successfully, else False
        """
        logging.info('scraper started')
        self.clear()
        product_name = product_name.strip().replace(" ", "+")
        url = f"https://www.skapiec.pl/szukaj/w_calym_serwisie/{product_name}/price/"       # /price/ means sort asc
        self.pid += 1       # new product new id
        try:
            self.page = self.get_page(url)      # get html content
            self.load_products()                # scrap html divs that contains all necessary information
            if self.products_boxes:
                self.load_products_info()           # extract information from divs (boxes)
                return True
            else:
                return False

        except ProductNotFoundException:
            return False
        except LoadingProductException:
            return False
        except ProductOverviewException:
            return False

    def load_products(self):
        """
        Loads html divs that hold all the information about the product.
        :return:    (None)
        """
        try:
            soup = BeautifulSoup(self.page, 'lxml')
            self.products_boxes = soup.find_all(class_=PRODUCT_CLASS)
            if not self.products_boxes:
                self.products_boxes = soup.find_all(class_="box-row js add-to-compare")

            logging.info('[load_products] found %s products', len(self.products_boxes))

        except Exception as e:
            logging.error(f'[load_products] error while parsing page: {str(e)}')
            raise LoadingProductException()

    def load_products_info(self):
        """
        Extracts products names, minimal prices and links to the list of stores that sale this product.
        Information are saved into self.products_overview variable.
        :return:    (None)
        """
        for product in self.products_boxes:
            try:
                name = product.find('h2', class_="title gtm_red_solink").text.strip()
                price = product.find('strong', class_="price gtm_sor_price").text
                price = float(price.replace("zł", "").replace(",", ".").replace(" ", "").replace("od", ""))
                href = product.find('a', href=True)['href']
                url_stores = self.base_url + href  # create full url link to detailed site
                p_overview = {'name': name, 'min_price': price, 'link': url_stores}
                self.products_overview.append(p_overview)

            except Exception as e:
                logging.error(f'[load_products_info] error while extracting product overview info: {e}')
                raise ProductOverviewException()

    # new version <------------------------------------------------------------------------------------
    def load_product_stores(self, num):
        """
        Returns an object that provides method to scrap offers of the product.
        :param num:     (int)   : index of products_overview from which method gets link
        :return:        (obj)   : instance of DetailedSite
        """
        if -1 < num < len(self.products_overview):
            url = self.products_overview[num]['link']
            return DetailedSite(url, self.pid)
        else:
            logging.error(f'[scrap_product] wrong argument passed to the function: {num}')
            raise OutOfBoundException()

    def scrap_nproducts(self, n, start=0, maxstores=5):
        """
        Simple method that scraps n products and returns list of scrapped products.
        :param n:           (int)   : number of products to be scrapped
        :param start:       (int)   : index of starting point of self.products_overview
        :param maxstores:   (int)   : number of stores that will be scrapped from one detailed site
        :return:
        """
        n = min(len(self.products_overview), n)
        products = []
        pid = 0     # not sure about that !TODO
        for k in range(start, n):
            url = self.products_overview[k]['link']
            pid += 1
            ds = DetailedSite(url, pid)
            ps = ds.scrap_nstores(maxstores)
            [products.append(p) for p in ps]
        return products
    # --------------------------------------------------------------------------------------------------

    def get_page(self, url):
        """
        Gets the page html content. If searching is unsuccessful then returns empty string.
        :param url:     (str)   : url of the site to scrap
        :return:        (str)   : html content of page. If site returns an error, returns empty string.
        """
        page = get_request(url)

        if self.is_found(page):
            return page
        else:
            return ""

    def is_found(self, page):
        """
        Checks whether the system found desired product or not.
        :param page:    (str)   : html content of the page
        :return:        (bool)  : True if page has been found, else False
        """
        try:
            soup = BeautifulSoup(page, 'lxml')
            msg_div = soup.find(class_="message only-header info")

            if msg_div:
                content = msg_div.find(class_="content")

                # if content.text == NO_RESULTS_STR:
                logging.warning(f"[is_found] page returned msg: {content.text}")
                raise ProductNotFoundException()
            else:
                return True

        except FeatureNotFound as e:
            logging.error(f'[is_found] probably you need to install lxml:  {e}')
            raise ProductNotFoundException()
        except TypeError as e:
            logging.error(f'[is_found] probably empty page was passed:  {e}')

    def get_products_overview(self):
        return self.products_overview

    def get_stores_num(self):
        """
        Returns number of products that has been found on the page
        :return:    (int)   : int in range <0, 20>
        """
        return len(self.products_overview)

    def clear(self):
        """
        Clear class variables, it is called before loading new page.
        :return:
        """
        self.products_boxes = []
        self.products_overview = []


class Product:

    def __init__(self, pid, name, price, delivery_costs, rating, rating_count, link, shop_name):
        """
        :param name:            (str)
        :param price:           (float)
        :param delivery_costs:  (list<float>)
        :param rating:          (float)
        :param rating_count:    (int)
        :param link:            (str)
        """
        self.pid = pid
        self.name = name.strip()
        self.price = price
        self.rating = rating
        self.rating_count = rating_count
        self.delivery_costs = delivery_costs
        self.max_delivery = max(delivery_costs)
        self.min_delivery = min(delivery_costs)
        self.link = link
        match = re.search(r'red/(\d+)/', self.link)
        self.store_id = match.group(1)
        self.shop_name = shop_name
        self.total_min_price = self.price + min(self.delivery_costs)
        self.total_max_price = self.price + max(self.delivery_costs)
        self.in_id = None
        self.count = 0

    def __str__(self):
        pid = '{:<12}  {:<12}\n'.format("Name: ", self.pid)
        name = '{:<12}  {:<12}\n'.format("Name: ", self.name)
        price = '{:<12}  {:<12}\n'.format("Price: ", self.price)
        rating = '{:<12}  {:<12}\n'.format("Rating: ", self.rating)
        rating_count = '{:<12}  {:<12}\n'.format("Opinions: ", self.rating_count)
        deliveries = '{:<12}  {:<12}\n'.format("Deliveries: ", str(self.delivery_costs))
        link = '{:<12}  {:<12}\n'.format("Link: ", self.link)
        store_id = '{:<12}  {:<12}\n'.format("Store ID: ", self.store_id)
        shop_name = '{:<12}  {:<12}\n'.format("Store: ", self.shop_name)
        return pid + name + price + rating + rating_count + deliveries + link + store_id + shop_name

    def __repr__(self):
        return f"({self.name}, {self.price}, {self.delivery_costs}, {self.rating}, {self.rating_count}," \
            f" sid: {self.store_id}, min_total: {self.total_min_price})"

if __name__ == "__main__":
    """
    Usage:
    - create an instance of SkapiecScraper class
    - try to load page, passing name of desired product
    - scrap 1 to 8 (7) pages
    - scrap() returns a list of (one) product from different stores [<Product_from_store1>, <Product_from_store2>, ...]

    sudo pip install lxml

    """
    ss = SkapiecScraper()
    product_name1 = "lenovo ideapad 320s"
    product_name2 = "samsung galaxy s10"
    product_name3 = "szczoteczka do zębów"
    product_name4 = "ładowarka do telefonssssu"
    product_name5 = "okulary przeciwsłoneczne czarne"
    product_name6 = 'agd'
    product_name7 = 'lodówka samsung rb'

    pr = 'materac'

    products_list = ["słuchawki sony", "fifa 20", "playstation 4",
                     "czarna koszula", "budzik", "myszka modecom",
                     "lampka nocna biała", "usb hub", "Zamiennik do HP",
                     "kurtka zimowa", "kurtka letnia", "kubek"
                     ]
    plimit = 10
    slimit = 20
    for pr in ["lodówka amica"]:
        logging.info(f'product: {pr}')
        if not ss.load_page(pr):
            print('Product not found')
        else:
            try:

                products = []
                for k in range(plimit):
                    ds1 = ss.load_product_stores(k)     # load k-product where k = 0,...,number of loaded products
                    ps = ds1.scrap_nstores(slimit, start=10)      # scrap n stores, starting from 10th store
                    [products.append(p) for p in ps]
                print(len(products))
                # [print(p) for p in products]

                ds2 = ss.load_product_stores(19)     # test out of bound
            except OutOfBoundException as e:
                print(str(e))
    logging.info('end scraping')


    # name = product.h2.get_text()
    # price_box = product.find(class_="price gtm_sor_price")
    # price = price_box.b.get_text()
    # price = float(price.replace("od", "").replace("zł", "").replace(",", ".").strip())
