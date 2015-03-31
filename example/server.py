import sys
import os.path as op
import backslant
from flask import Flask, render_template

sys.meta_path.insert(0, backslant.PymlFinder(op.dirname(__file__), hook="bsviews"))

from bsviews.templates import index

app = Flask(__name__)
app.debug = True

@app.route('/')
def hello_world():
    s = ''.join(index.render(title="Backslant Sample Server"))
    return s

@app.route('/j2')
def j2():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9000)