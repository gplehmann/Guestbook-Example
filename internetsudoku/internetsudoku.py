import urllib2
import re
import datetime

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

class Puzzle(db.Model):
    """A Sudoku puzzle entry with a URL, character representation, difficulty
    and date

    """
    URL = db.StringProperty()
    #Because of the limitations of templates, it's easier to store the puzzle as
    #9 separate rows instead of as one 81-character string
    row_1 = db.StringProperty()
    row_2 = db.StringProperty()
    row_3 = db.StringProperty()
    row_4 = db.StringProperty()
    row_5 = db.StringProperty()
    row_6 = db.StringProperty()
    row_7 = db.StringProperty()
    row_8 = db.StringProperty()
    row_9 = db.StringProperty()
    difficulty = db.StringProperty()
    date = db.DateTimeProperty(auto_now_add=True)


def puzzle_key(puzzle_name=None):
    return db.Key.from_path('Puzzle', puzzle_name or 'default_puzzle')


class MainPage(webapp.RequestHandler):
    def get(self):
        puzzle_name = self.request.get('puzzle_name')
        puzzles_query = Puzzle.all().ancestor(
            puzzle_key(puzzle_name)).order('-date')
        puzzles = puzzles_query.fetch(3)

        template_values = {
            'puzzles': puzzles,
        }

        path = os.path.join(os.path.dirname(__file__), 'templates/solvedpuzzles.html')
        self.response.out.write(template.render(path, template_values))

#TODO: add a self parameter if this gets moved into a class
def pull_websudoku(difficulty=1)
    puzzle_page = urllib2.urlopen('http://view.websudoku.com/?level=' + difficulty)
    puzzle_regex = re.compile('<TABLE.*?>(<TR>>(<TD.*?><INPUT.*?></TD>){9}</TR>){9}</TABLE>', re.IGNORECASE)
    puzzle_HTML = ''

    #Find the line from the page that contains the HTML code for the puzzle
    for line in puzzle_page:
        if puzzle_regex.match(line):
            puzzle_HTML = line
            break

    #TODO: Format the HTML into a 9x9 list matrix
    

application = webapp.WSGIApplication(
                                     [('/', MainPage)],
                                     debug=True)


def main():
    run_wsgi_app(application)


if __name__ == "__main__":
    main()
