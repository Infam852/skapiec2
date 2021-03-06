from flask import Flask, render_template, url_for, flash, redirect, request
from forms import ProductForm
from main3 import *

app = Flask(__name__)
app.config['SECRET_KEY'] = 'd74d200efebb8016d462d9127428d243'
so = SkapiecOptimizer()


@app.route("/", methods=['GET', 'POST'])     # main page (i.e. root page)
def home():
    form = ProductForm()
    if form.validate_on_submit():


        if so.add_product(form.name.data, form.count.data, form.min_price.data,
                          form.max_price.data, form.min_rating.data, form.nrates.data):
            flash('Produkt dodany pomyślnie!', 'success')
        else:
            flash('Nie możesz dodać więcej niż 5 produktów', 'danger')
        return redirect(url_for('home'))

    form.count.data = DEFAULT_COUNT
    form.min_price.data = DEFAULT_MIN_PRICE
    form.max_price.data = DEFAULT_MAX_PRICE
    form.min_rating.data = DEFAULT_RATING
    form.nrates.data = DEFAULT_MIN_NRATES
    return render_template('home.html', form=form, products=so.in_products)


@app.route("/new-search", methods=['GET', 'POST'])     # main page (i.e. root page)
def new_search():
    so.clear_products()
    return redirect(url_for('home'))


@app.route('/search', methods=['POST'])
def search():
    if not so.in_products:
        flash('Najpierw dodaj produkty', 'warning')
        return redirect(url_for('home'))

    so.search()
    results, msgs = so.find_best()
    for msg in msgs:
        flash(msg, 'warning')

    return render_template('results2.html', results=results)       # render results template


@app.route('/delete/<int:pid>', methods=['GET', 'POST'])
def delete_product(pid):
    if so.remove_product(pid):
        flash('Produkt został wycofany', 'success')
    else:
        flash('Wystąpił błąd', 'danger')
    return redirect(url_for('home'))


def result_reformat(results):
    results_ = []
    for offers in results:
        print('****OFFER******')
        for product in offers:
            print(product)


if __name__=="__main__":
    app.run(debug=True)
