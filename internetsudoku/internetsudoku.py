import urllib2
import re
import datetime
import random
import os
import logging

#import sudoku solving module

from google.appengine.api import memcache
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app


class Puzzle(db.Model):
    """A Sudoku puzzle entry with a URL, character representation, difficulty
    and date

    """
    URL = db.StringProperty()
    puzzle_string = db.StringProperty()
    difficulty = db.StringProperty()
    date = db.DateTimeProperty(auto_now_add=True)


class PuzzleParseError(Exception): pass


def puzzle_key(puzzle_name=None):
    """Returns a datastore key for a Puzzle entity"""
    return db.Key.from_path('Puzzle', puzzle_name or 'default_puzzle')


class MainPage(webapp.RequestHandler):
    """Displays the last three solved puzzles"""
    MEMCACHE_TIMEOUT = 60
    MEMCACHE_KEY = 'puzzles'
    def get(self):
        logging.info('Request for recently solved puzzles received.')
        puzzles = self.__get_data()

        template_values = {
            'puzzles': puzzles,
        }

        logging.info('Sending puzzles to template for output.')
        path = os.path.join(os.path.dirname(__file__), 'templates/solvedpuzzles.html')
        self.response.out.write(template.render(path, template_values))
        logging.info('Request processed.')

    def __get_data(self):
        """Get data from the memcache if present, otherwise pull it from the datastore and keep it in the
        memcache for 10 minutes.
        
        """
        puzzles_html = memcache.get(self.MEMCACHE_KEY)
        if puzzles_html:
            logging.info('Retrieved puzzles from Memcache.')
            return puzzles_html
        else:
            puzzles = Puzzle.all().ancestor(puzzle_key()).order('-date').fetch(3)
            puzzles_html = []
            for puzzle in puzzles:
                puzzles_html_str = '<table border="1" cellspacing="0"><tr><th colspan="9">Solved <b>%s</b></th></tr> \
<tr><th colspan="9">Difficulty: <b>%s</b></th></tr>' % (puzzle.date, puzzle.difficulty)
                counter = 0
                for cell in puzzle.puzzle_string:
                    if counter % 9 == 0: #we're at the start of a new row
                        puzzles_html_str += '<tr>'
                    puzzles_html_str += '<td align="center">%s</td>' % cell
                    if counter % 9 == 8: #we're at the end of a row
                        puzzles_html_str += '</tr>'
                    counter += 1
                puzzles_html_str += '</table><br/>'
                puzzles_html.append(puzzles_html_str)

            logging.info('Caching puzzle html.')
            if not memcache.add(self.MEMCACHE_KEY, puzzles_html, self.MEMCACHE_TIMEOUT):
                logging.error("Memcache set failed.")
            return puzzles_html


class GetPuzzle(webapp.RequestHandler):
    """Invoked by the cron job to pull (and eventually solve) new puzzles."""
    def get(self):
        try:
            sudoku_puzzle = Websudoku(random.randint(1,4))
        except PuzzleParseError, e:
            logging.error('Error parsing sudoku puzzle: \n' + str(e.args))
        else:
            #invoke sudoku puzzle solver here
            sudoku_puzzle.store_puzzle()


class Websudoku:
    """A class to pull a sudoku puzzle from a URL and attempt to parse it as if it came from the Websudoku site."""
    def __init__(self, difficulty=1, URL='http://view.websudoku.com/', difficulty_level_str='?level='):
        """Initializes a Websudoku instance with a difficulty and URL, and pulls and parses HTML from the URL.

        Keyword arguments:
        difficulty -- an integer representation of the difficulty to use with the URL
            1 = EASY, 2 = MEDIUM, 3 = HARD, 4 = EVIL (default 1)
        URL -- The URL string to pull HTML from to parse for a sudoku puzzle (default http://view.websudoku.com/)
        difficulty_level_str -- string to add to the URL for the GET request for the difficulty (default ?level=)

        """
        self.URL = URL
        self.difficulty = difficulty
        self.difficulty_level_str = difficulty_level_str
        self.puzzle = self.sudoku_html_to_list(self.pull_sudoku())


    def pull_sudoku(self):
        """Pull a Websudoku puzzle from the URL with this instance's difficulty, returning the HTML.

        Raises PuzzleParseError if it is unable to match an HTML sudoku string in the format Websudoku uses.

        """
        full_URL = self.URL + self.difficulty_level_str + str(self.difficulty)
        puzzle_page = urllib2.urlopen(full_URL)
        logging.info('Pulled HTML from ' + full_URL)
        puzzle_regex = re.compile('<TABLE.*?>(<TR>(<TD.*?><INPUT.*?></TD>){9}</TR>){9}</TABLE>', re.IGNORECASE)
        puzzle_HTML = ''

        #Find the line from the page that contains the HTML code for the puzzle
        for line in puzzle_page:
            if puzzle_regex.match(line):
                puzzle_HTML = line.strip()
                logging.info('HTML matched regex.')
                break

        if puzzle_HTML == '':
            raise PuzzleParseError, ('Unable to pull a valid HTML representation of a sudoku puzzle',)
        return puzzle_HTML


    def sudoku_html_to_list(self, html_str):
        """Convert sudoku puzzle from HTML to a list matrix and return the list.

        Raises PuzzleParseError if 81 cells are not parsed from the HTML.

        """
        logging.info('Converting HTML to list matrix.')
        empty_regex = re.compile('<INPUT.*?onBlur.*?>', re.IGNORECASE)
        full_regex = re.compile('<INPUT.*?READONLY VALUE="(\d)".*?>', re.IGNORECASE)

        #Remove extraneous HTML and change <TD> tags into a delimiter we can split on
        html_str = re.sub(re.compile('</?TABLE.*?>|</?TR>', re.IGNORECASE), '', html_str)
        html_str = re.sub(re.compile('</?TD.*?>', re.IGNORECASE), '|', html_str)
        html_str = html_str.split('|')
        puzzle = [[]]
        row = 0
        col = 0
        counter = 0

        #parse the HTML and convert <INPUT> tags into either empty or full cells in a 9x9 sudoku grid
        for cell in html_str:
            if cell:
                empty_match = empty_regex.match(cell)
                full_match = full_regex.match(cell)
                if empty_match:
                    puzzle[row].append('0')
                elif full_match:
                    puzzle[row].append(full_match.group(1))
                else:
                    raise PuzzleParseError, ('Puzzle has an invalid cell at position ' + str(row) + "," + str(col), )
                col += 1
                if col > 8:
                    col = 0
                    row += 1
                    if row <= 8:
                        puzzle.append([])

                counter += 1

        if counter != 81:
            raise PuzzleParseError, ('Puzzle derived from the HTML parameter was not a 9x9 grid',)

        return puzzle


    def store_puzzle(self, puzzle_name=None):
        """Store this instance's puzzle in the datastore.

        Keyword arguments:
        puzzle_name -- used to generate a key for the datastore (default None)

        """
        logging.info('Storing puzzle in the datastore.')
        #Convert puzzle into nine 9-character strings for storage
        entity_row = []
        puzzle_string = ''
        for row in self.puzzle:
            for number in row:
                puzzle_string += str(number)

        #Convert the numeric difficulty to a string
        if self.difficulty == 1:
            str_difficulty = 'EASY'
        elif self.difficulty == 2:
            str_difficulty = 'MEDIUM'
        elif self.difficulty == 3:
            str_difficulty = 'HARD'
        elif self.difficulty == 4:
            str_difficulty = 'EVIL'
        else:
            str_difficulty = 'UNKNOWN'
            
        puzzle_entity = Puzzle(parent=puzzle_key(puzzle_name))
        puzzle_entity.puzzle_string = puzzle_string
        puzzle_entity.difficulty = str_difficulty
        puzzle_entity.put()


application = webapp.WSGIApplication(
                                     [('/', MainPage),
                                      ('/getpuzzle', GetPuzzle)],
                                     debug=True)


def main():
    logging.getLogger().setLevel(logging.DEBUG)
    run_wsgi_app(application)


if __name__ == "__main__":
    main()
