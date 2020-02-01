from scraper2 import *
import time
import threading
import logging
from settings import *
from exceptions import *


class SkapiecOptimazer:

    def __init__(self):
        self.scrap_threads = []
        self.scraper = SkapiecScraper()
        self.in_products = []   # list of user requirements

    def clear_products(self):
        self.in_products = []

    def add_product(self, name, count, min_price, max_price, min_rating, nrates):
        """
        Add user product
        :param name:
        :param count:
        :param min_price:
        :param max_price:
        :param min_rating:
        :param nrates:
        :return:
        """
        if len(self.in_products) >= 5:
            logging.warning('[ADD_PRODUCT] You can not add more then 5 products to the cart')
            return False
        # user_req = {'name': name, 'min_price': min_price, 'max_price': max_price, 'count': count,
        #             'min_rating': min_rating, 'nrates': nrates, 'found_products': None}
        user_req = UserRequirements(name, count, min_price, max_price, min_rating, nrates)
        self.in_products.append(user_req)
        return True

    def search(self):
        # Iterate through user's shopping basket and search for offers
        for user_req in self.in_products:
            plist = ProductList(user_req.name, self.scraper)
            try:
                plist.load_products()
            except ProductNotFoundException:
                logging.info('[SEARCH] Product "{}" not found'.format(user_req.name))
            user_req.found_products = plist

        # print results
        # for poffer in self.in_products:
        #     plist = poffer['found_products']
        #     print("LENGTH:", len(plist.products_list))
        #     [print(repr(p)) for p in plist.products_list]

    def find_best(self):
        algorithm_handler = AlgorithmHandler(self.in_products)
        return algorithm_handler.find(), algorithm_handler.msgs

    def print_products(self):
        for p in self.in_products:
            pass


class ProductList:
    def __init__(self, pname, scraper):
        self.pname = pname
        self.scraper =scraper
        self.scrap_threads = []
        self.products_list = []

    def load_products(self):
        """
        Main method it should be called after class initialization.
        It loads the maximum number of offers and stores that were specified in settings.
        Loaded products are saved in a list and returned.
        It can throw ProductNotFoundException if there is no product with specified name.
        It can return an empty list if all stores have not specified delivery costs.
        :return:    (list)  : sorted list of products (sort by total minimum price)
        """
        if not self.init_scraper():
            raise ProductNotFoundException()

        self.init_threads()
        self.start_threads()

        self.products_list.sort(key=lambda x: x.total_min_price, reverse=False)
        # [print(p) for p in self.products_list]
        return self.products_list

    def init_scraper(self):
        """
        Initialize scraper - load search results
        :return:
        """
        if self.scraper.load_page(self.pname):
            return True
        else:
            return False

    def init_threads(self):
        offers = self.scraper.get_stores_num()
        offers = offers if offers <= MAX_OFFERS else MAX_OFFERS

        for k in range(offers):
            x = threading.Thread(target=self.get_offer, args=(k,))      # k - index of offer
            self.scrap_threads.append(x)

    def start_threads(self):
        [x.start() for x in self.scrap_threads]
        [x.join() for x in self.scrap_threads]
        logging.info('[SkapiecOptimazer] products have been loaded')

    def get_offer(self, k):
        """
        Scrap one offer
        :param k:
        :return:
        """
        try:
            ds = self.scraper.load_product_stores(k)
            products = ds.scrap_nstores(MAX_STORES)
            self.products_list.extend(products)

        except OutOfBoundException as e:
            print(str(e))

    def apply_requirements(self, min_price=DEFAULT_MIN_PRICE, max_price=DEFAULT_MAX_PRICE,
                           min_rating=DEFAULT_RATING, nrates=DEFAULT_MIN_NRATES):
        """
        Applies requirements to product. Returns list of products that satisfy requirements.
        It might be an empty list if there is not product that meets requirements.
        :param min_price:
        :param max_price:
        :param min_rating:
        :param nrates:
        :return:
        """
        out_list = []
        for p in self.products_list:
            if max_price > p.price > min_price and p.rating > min_rating and p.rating_count > nrates:
                out_list.append(p)
        return out_list

class UserRequirements:

    def __init__(self, name, count=DEFAULT_COUNT, min_price=DEFAULT_MIN_PRICE, max_price=DEFAULT_MAX_PRICE,
                           min_rating=DEFAULT_RATING, nrates=DEFAULT_MIN_NRATES):
        self.name = name
        self.count = count
        self.min_price = min_price
        self.max_price = max_price
        self.min_rating = min_rating
        self.nrates = nrates
        self.found_products = []



class AlgorithmHandler:

    def __init__(self, in_products):
        self.in_products = in_products
        self.dummy_cheapest = []
        self.msgs = []

    def load_cheapest_products(self, processed_products):
        """
        Creates map of cheapest products.
        :return:
        """
        for idx, offers in enumerate(processed_products):
            if offers:
                off = offers[0]
                off.in_id = idx
                self.dummy_cheapest.append(off)
            else:
                self.dummy_cheapest.append(None)

        print('CHEAPEST NOW')
        [print(repr(p)) for p in self.dummy_cheapest]

    def check_dummy(self):
        """
        Checks if all cheapest products have free delivery
        :return:
        """
        logging.info('[CHECK DUMMY]----------------------------')
        for product in self.dummy_cheapest:
            if product is None:
                logging.info('[CHECK DUMMY] product is None')
                continue
            if not min(product.delivery_costs) == 0.00:
                return False
            logging.info(f'[CHECK DUMMY] {product.name} ok')
        return True

    def find(self):     # !TODO only one product -> just return cheapest
        self.msgs = []
        if not self.in_products:
            logging.info('[FIND] in_products list is empty')
            return None

        processed_products = []  # list of products offers that meet requirements
        for user_req in self.in_products:
            plist = user_req.found_products
            logging.info(f'[FIND] Start processing: {user_req.name}, input_len: {len(plist.products_list)}')
            # print('*************BEFORE********************')
            # [print(p) for p in plist.products_list]
            # print('****************************************')
            req_plist = plist.apply_requirements(min_price=user_req.min_price, max_price=user_req.max_price,
                                                 min_rating=user_req.min_rating, nrates=user_req.nrates)
            # print('*************AFTER*********************')
            # [print(p) for p in req_plist]
            # print('****************************************')
            if not req_plist:   # if there are no offers (of this product) that meet requirements
                processed_products.append(plist.products_list)  # add all offers
                logging.info(f'[FIND] product {user_req.name} does not meet requirements')
                if plist.products_list:
                    self.msgs.append(f'{user_req.name} nie spełnia wymagań, wyszukano bez uwzględniania kryteriów')
                else:
                    self.msgs.append(f'Nie znaleziono produktu: {user_req.name}')
            else:
                processed_products.append(req_plist)
                logging.info(f'[FIND] product {user_req.name} meets requirements')
        # print(processed_products)

        self.load_cheapest_products(processed_products)
        # if self.check_dummy():
        #     logging.info('[FIND] all cheapest products have free delivery')
        #     return self.dummy_cheapest

        out = self.get_cheapest(processed_products)
        for off in out:
            print('LEN: ', len(off), off)

        # print('************BEFORE REDUCED******************')
        # [print(repr(p)) for p in processed_products]
        # print('********************************************')
        # # try to find better sets (take into consideration products from the same shop)
        # for k in range(len(processed_products)):
        #     processed_products[k] = self.reduce(processed_products[k])
        #
        # print('*****************REDUCED*********************')
        # [print(repr(p)) for p in processed_products]
        # print('********************************************')
        #
        # print('**************CREATE OFFERS*****************')
        # self.create_offers(processed_products)
        # print()

        return out

    def reduce(self, products_list):
        """
        Leave only offer with lowest price from one shop and remove offers which have higher price without
        delivery then currently cheapest offer for the product.
        :return:        (list) :
        """
        if not products_list:
            return []
        products_list.sort(key=lambda x: x.total_min_price, reverse=False)
        cheapest_offer = products_list[0]
        print('***CHEAPEST****')
        print(repr(cheapest_offer))
        print('***************')
        stores_id = []
        out_offers = []

        for product in products_list:
            if product.price > cheapest_offer.total_min_price:  # might be equal (e.g. product = cheapest_offer)
                continue    # !TODO can be break, because list is sorted

            if product.store_id not in stores_id:
                out_offers.append(product)
                stores_id.append(product.store_id)
        return out_offers

    def create_offers(self, products_offers):
        stores_map = {}
        for offers in products_offers:
            for offer in offers:
                if offer.store_id not in stores_map.keys():
                    stores_map[offer.store_id] = [offer]
                else:
                    stores_map[offer.store_id].append(offer)

        print(stores_map)
        reduced_stores_map = {}
        # remove entries with only one element
        for store_id, offers in stores_map.items():
            if len(offers) > 1:
                reduced_stores_map[store_id] = offers
        print('REDUCED STORES MAP ')
        print(reduced_stores_map)
        # if not reduced_stores_map:
        #     final_offers = self.get_cheapest()
        # else:
        final_offers = self.make_offer(reduced_stores_map)
        print("*************END***************")
        return reduced_stores_map

    def get_cheapest(self, products_list):
        """
        Should return three "cheapest" offers
        :param products_list:
        :return:    (list) : list of best offers
        """
        print('LEN PL: ', len(products_list))
        print(products_list[0])
        print('*******************************************************')
        products_sets = []
        products_sets.append(self.dummy_cheapest)
        for k in range(1, RETURNED_SETS):
            set_list = []
            for j in range(len(products_list)):
                try:
                    product = products_list[j][k]
                    product.in_id = j
                except IndexError:
                    product = None
                print('ADD PRODUCT:', repr(product))
                set_list.append(product)
            products_sets.append(set_list)
            print('SET LIST: ', set_list)
        return products_sets

    def make_offer(self, reduced_stores_map):
        final_offers = []
        for store_id, offers in reduced_stores_map.items():
            pids = [offer.pid for offer in offers]
            # print(pids)
            not_in_map_products = [product for product in self.dummy_cheapest if product.pid not in pids]
            # [print(p.name, p.pid) for p in self.dummy_cheapest]
            # print('NOT IN MAP')
            # print(self.dummy_cheapest)
            # print(not_in_map_products)
            foffer = offers
            foffer.extend(not_in_map_products)
            final_offers.append(foffer)
        print('**********FINAL OFFERS************')
        print(final_offers)
        return final_offers

if __name__ == "__main__":
    product_name1 = "lenovo ideapad 320s"
    product_name2 = "samsung galaxy s10"
    product_name3 = "szczoteczka do zębów"
    product_name4 = "ładowarka do telefonssssu"
    product_name5 = "okulary przeciwsłoneczne czarne"
    product_name6 = 'agd'
    product_name7 = 'lodówka samsung rb'
    product_name8 = 'słuchawki Omen'
    product_name9 = 'rival 100'     # rival 110
    product_name10 = 'monitor 24 samsung'
    product_name11 = 'monitor 24 lg'

    so = SkapiecOptimazer()
    so.add_product(product_name9, DEFAULT_COUNT, DEFAULT_MIN_PRICE, DEFAULT_MAX_PRICE, DEFAULT_RATING, DEFAULT_MIN_NRATES)
    so.add_product(product_name10, DEFAULT_COUNT, DEFAULT_MIN_PRICE, DEFAULT_MAX_PRICE, DEFAULT_RATING, DEFAULT_MIN_NRATES)
    so.add_product(product_name11, DEFAULT_COUNT, DEFAULT_MIN_PRICE, DEFAULT_MAX_PRICE, DEFAULT_RATING, DEFAULT_MIN_NRATES)
    # so.add_product(product_name3, DEFAULT_COUNT, DEFAULT_MIN_PRICE, DEFAULT_MAX_PRICE, DEFAULT_RATING, DEFAULT_MIN_NRATES)
    # so.add_product(product_name4, DEFAULT_COUNT, DEFAULT_MIN_PRICE, DEFAULT_MAX_PRICE, DEFAULT_RATING, DEFAULT_MIN_NRATES)
    # so.add_product(product_name5, DEFAULT_COUNT, DEFAULT_MIN_PRICE, DEFAULT_MAX_PRICE, DEFAULT_RATING, DEFAULT_MIN_NRATES)

    start = time.time()
    so.search()
    so.find_best()

    end = time.time()
    print("TIME NEEDED TO FOUND 5 PRODUCTS:", end-start, "s")