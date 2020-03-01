from scraper2 import *
import time
import threading
import logging
from settings import *
from exceptions import *

NULL_PRODUCT = Product(-100, '', 0, [0.00], 0, 0, 'link/red/9999999/1', '')
# ^&%^G&T^%^& returns results :)


class SkapiecOptimizer:

    def __init__(self):
        self.scrap_threads = []
        self.scraper = SkapiecScraper()
        self.in_products = []   # list of user requirements
        self.req_id = 1

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

        user_req = UserRequirements(self.req_id, name, count, min_price, max_price, min_rating, nrates)
        self.req_id += 1
        self.in_products.append(user_req)
        return True

    def remove_product(self, pid):
        """
        Remove product from user's basket
        :param pid:     (int)       : user requirements (aka product) id
        :return:        (boolean)   : True if given id was found in a list
        """
        in_len = len(self.in_products)
        for k in range(in_len):
            user_req = self.in_products[k]
            if user_req.pid == pid:
                self.in_products.remove(user_req)
                return True
        return False

    def search(self):
        # Iterate through user's shopping basket and search for offers
        for user_req in self.in_products:
            plist = ProductList(user_req.name, user_req.count, self.scraper)
            try:
                plist.load_products()
            except ProductNotFoundException:
                logging.info('[SEARCH] Product "{}" not found'.format(user_req.name))
            user_req.found_products = plist

    def find_best(self):        # !TODO search() can be moved here
        algorithm_handler = AlgorithmHandler(self.in_products)
        return algorithm_handler.find(), algorithm_handler.msgs


class ProductList:
    """ List of offers of one product """

    def __init__(self, pname, count, scraper):
        self.pname = pname
        self.count = count
        self.scraper = scraper
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

        self.products_list.sort(key=lambda x: (x.total_min_price, -x.rating), reverse=False)     # !TODO
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
            for p in products:
                p.count = self.count
            self.products_list.extend(products)

        except OutOfBoundException as e:
            logging.error(f'[GET_OFFER] scraper cannot load offer with index k={k}, {str(e)}')

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
    """ Represents user entry """

    def __init__(self, pid, name, count=DEFAULT_COUNT, min_price=DEFAULT_MIN_PRICE, max_price=DEFAULT_MAX_PRICE,
                           min_rating=DEFAULT_RATING, nrates=DEFAULT_MIN_NRATES):
        self.pid = pid
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
        self.possible_offers = []       # list of ResultSets

    def load_cheapest_products(self, processed_products):
        """
        Creates map of cheapest products.
        :return:
        """
        products_set = ResultSet()

        for idx, offers in enumerate(processed_products):
            if offers:
                off = offers[0]
                off.in_id = idx     # assign product index
                products_set.add_product(off)

            else:
                products_set.add_product(None)
        products_set.calculate_total_price()        # !TODO remember of it

        self.possible_offers.append(products_set)
        self.dummy_cheapest = products_set

    def find(self):
        self.msgs = []  # reset
        if not self.in_products:
            logging.warning('[FIND] in_products list is empty')
            return []

        # [[p1_off1, p1_off2 ...], [ p2_off1, ...]]
        processed_products = []  # list of products and its offers that meet requirements (or not)
        for user_req in self.in_products:
            plist = user_req.found_products
            if not plist.products_list:
                processed_products.append([])
                self.msgs.append(f'Nie znaleziono produktu: {user_req.name}')
                continue

            logging.info(f'[FIND] Start processing: {user_req.name}, input_len: {len(plist.products_list)}')

            # filter offers by user requirements
            filtered_plist = plist.apply_requirements(min_price=user_req.min_price, max_price=user_req.max_price,
                                                      min_rating=user_req.min_rating, nrates=user_req.nrates)

            if not filtered_plist:  # no offers (of this product) that meet requirements
                logging.info(f'[FIND] product {user_req.name} does not meet requirements')
                processed_products.append(plist.products_list)  # add all offers, ignore requirements
                self.msgs.append(f'{user_req.name} nie spełnia wymagań, wyszukano bez uwzględniania kryteriów')

            else:
                processed_products.append(filtered_plist)
                logging.info(f'[FIND] product {user_req.name} meets requirements')

        self.load_cheapest_products(processed_products)

        dummy_cheapest = self.get_cheapest(processed_products)
        dummy_cheapest.sort(key=lambda x: (-x.not_none_products, x.total_price), reverse=False)

        return dummy_cheapest

    def reduce(self, products_list):
        """
        Leave only offer with lowest price from one shop and remove offers which have higher price without
        delivery then currently cheapest offer for the product.
        :return:        (list) :
        """
        if not products_list:
            return []
        products_list.sort(key=lambda x: (x.total_min_price, -x.rating), reverse=False)
        cheapest_offer = products_list[0]
        # print('***CHEAPEST****')
        # print(repr(cheapest_offer))
        # print('***************')
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
        for offers in products_offers:  # create map {store_id: [product1, product2, ...]}
            for offer in offers:
                if offer.store_id not in stores_map.keys():
                    stores_map[offer.store_id] = [offer]
                else:
                    stores_map[offer.store_id].append(offer)

        reduced_stores_map = {}
        # remove entries with only one element
        for store_id, offers in stores_map.items():
            if len(offers) > 1:
                reduced_stores_map[store_id] = offers

        if not reduced_stores_map:
            return []
        final_offers = self.make_offer(reduced_stores_map)

        return final_offers

    def make_offer(self, reduced_stores_map):
        final_offers = []
        for store_id, products in reduced_stores_map.items():     # try to find a set of products form one store
            pids = [product.pid for product in products]
            not_in_map_products = []  # [product for product in self.dummy_cheapest.products if product.pid not in pids]
            for product in self.dummy_cheapest.products:
                if product:
                    if product.pid not in pids:
                        not_in_map_products.append(product
                                                   )
            resultSet = ResultSet()
            resultSet.add_products_list(products)
            resultSet.add_products_list(not_in_map_products)
            resultSet.calculate_total_price()
            final_offers.append(resultSet)

        return final_offers

    def get_cheapest(self, products_list):
        """
        Should return three "cheapest" offers
        :param products_list:
        :return:    (list) : list of best offers
        """
        products_sets = [self.dummy_cheapest]
        for k in range(1, RETURNED_SETS):       # we want to create 3 sets
            set_list = ResultSet()
            for j in range(len(products_list)):     # add offer of each kind of product user desires
                try:
                    product = products_list[j][k]
                    product.in_id = j
                except IndexError:
                    # product = self.dummy_cheapest.products[j]       # !TODO ******************************************
                    product = None
                set_list.add_product(product)
            set_list.calculate_total_price()
            products_sets.append(set_list)
        return products_sets

    def get_best_offers(self, stores_set, dummy_sets):
        # check for duplicates
        all_sets = []
        for sset in stores_set:
            if sset.is_equal(dummy_sets[0]) or sset.is_equal(dummy_sets[1]) or sset.is_equal(dummy_sets[2]):
                continue
            all_sets.append(sset)

        all_sets.extend(dummy_sets)
        all_sets.sort(key=lambda x: (-x.not_none_products, x.total_price))

        return [all_sets[0], all_sets[1], all_sets[2]]


class ResultSet:

    def __init__(self):
        self.products = []
        self.total_price = 0
        self.stores_ids = []
        self.deliveries = {}    # map {store_id: list of deliveries}
        self.not_none_products = 0

    def add_products(self, *products):
        for p in products:
            self.add_product(p)
        self.calculate_total_price()

    def add_products_list(self, plist):
        for p in plist:
            self.add_product(p)

    def add_product(self, product):
        if product is None:
            self.products.append(NULL_PRODUCT)
            return

        for p in self.products:
            if p == NULL_PRODUCT or p is None:
                continue
            # if p.pid == product.pid:
            #     raise UniqueIdException()   # set should contain only unique products
        self.products.append(product)

    def update_total_price(self, product):
        pstore_id = product.store_id
        self.total_price += product.count*product.price
        self.stores_ids.append(pstore_id)

        if pstore_id in self.deliveries.keys():
            self.deliveries[pstore_id].extend(product.delivery_costs)
        else:
            self.deliveries[pstore_id] = product.delivery_costs

    def calculate_total_price(self):
        """
        Calculates total price of all products in the sets.
        It takes into consideration products from the same store:
        - all products from different stores - take min delivery cost for every
        - 2 products from one store - take maximum delivery cost
        :return:
        """
        self.total_price = 0
        self.not_none_products = 0      # count how many products is not None
        self.products.sort(key=lambda x: x.price)
        for p in self.products:
            if p is None or p == NULL_PRODUCT:
                continue
            self.update_total_price(p)
            self.not_none_products += 1

        for store_id in set(self.stores_ids):
            if self.stores_ids.count(store_id) > 1:
                self.total_price += max(self.deliveries[store_id])
            else:
                self.total_price += min(self.deliveries[store_id])


    def is_equal(self, other_set):
        """
        Returns True if other_set contains exactly (references equality) the same products
        :param other_set:       (ResultSet)
        :return:                (boolean)
        """
        other_products = other_set.products
        for p, op in zip(self.products, other_products):
            if p != op:
                return False

        return True


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

    so = SkapiecOptimizer()
    so.add_product(product_name9, DEFAULT_COUNT, DEFAULT_MIN_PRICE, DEFAULT_MAX_PRICE, DEFAULT_RATING, DEFAULT_MIN_NRATES)
    so.add_product(product_name10, DEFAULT_COUNT, DEFAULT_MIN_PRICE, DEFAULT_MAX_PRICE, DEFAULT_RATING, DEFAULT_MIN_NRATES)
    so.add_product(product_name11, DEFAULT_COUNT, DEFAULT_MIN_PRICE, DEFAULT_MAX_PRICE, DEFAULT_RATING, DEFAULT_MIN_NRATES)
    # so.add_product(product_name3, DEFAULT_COUNT, DEFAULT_MIN_PRICE, DEFAULT_MAX_PRICE, DEFAULT_RATING, DEFAULT_MIN_NRATES)
    # so.add_product(product_name4, DEFAULT_COUNT, DEFAULT_MIN_PRICE, DEFAULT_MAX_PRICE, DEFAULT_RATING, DEFAULT_MIN_NRATES)
    # so.add_product(product_name5, DEFAULT_COUNT, DEFAULT_MIN_PRICE, DEFAULT_MAX_PRICE, DEFAULT_RATING, DEFAULT_MIN_NRATES)

    start = time.time()
    so.search()

    al = AlgorithmHandler(so.in_products)
    al.find()

    # p1 = Product(1, "Telefon", 20, [5.00, 7.00, 50.00], 1, 1, 'abc.com/red/50/25', 'shop')
    # p1.count = 1
    # p2 = Product(2, "Telewizor", 420, [13.00, 7.00, 25.00], 1, 1, 'abc.com/red/15/155', 'shop')
    # p2.count = 1
    # p3 = Product(3, "Myszka", 100, [6.50, 7.00, 50.00], 1, 1, 'abc.com/red/10/21', 'shop')
    # p3.count = 1
    # p4 = None
    #
    # rs = ResultSet()
    # rs.add_product(p1)
    # rs.add_product(p2)
    # rs.add_product(p3)
    # rs.add_product(p4)
    # rs.calculate_total_price()

    end = time.time()
    print("TIME NEEDED TO FIND 5 PRODUCTS:", end-start, "s")
