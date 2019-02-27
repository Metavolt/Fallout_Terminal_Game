#!/usr/bin/python -*- coding: utf-8 -*-
"""This is a basic recreation of the RobCo terminal hacking mini-game
found in the Bethesda Fallout games and is playable in any Unix shell"""
import curses
import passwordgen
import locale
import random
import string
import simpleaudio
import os
import sys
from gpiozero import Button, DigitalOutputDevice

button_up = Button(20)
button_down = Button(16)
button_left = Button(12)
button_right = Button(13)
button_enter = Button(6)
button_quit = Button(5)
trinket_trigger = DigitalOutputDevice(26)

buttons = [button_up, button_down, button_left, button_right, button_enter, button_quit]

os.chdir('/home/pi/Fallout_Terminal_Game/venv')

sfx_good = simpleaudio.WaveObject.from_wave_file('passgood.wav')
sfx_bad = simpleaudio.WaveObject.from_wave_file('passbad.wav')
sfx_dud = simpleaudio.WaveObject.from_wave_file('passdud.wav')
sfx_reset = simpleaudio.WaveObject.from_wave_file('passreset.wav')
locale.setlocale(locale.LC_ALL, '')
code = locale.getpreferredencoding()

class TerminalGame:

    def __init__(self):
        self.button_idle = True
        self.logged_in = False
        self.locked_out = False
        self.terminal_status = 'Accessible'
        self.attempts = 4
        self.likeness = 0
        self.test_result = ''
        self.address = 0
        self.rows = 16
        self.word_length = 5 # Password length from 4 to 14
        self.num_words = 12
        self.selectable_size = 384 # 16 rows of 12 char columns
        self.side_text_size = 225 # 15 rows of 15 char columns
        self.max_spacing = 0
        self.word_list = []
        self.word_start_locations = []
        self.side_text = []
        self.selectable_text = []
        self.selection_length = 1
        self.selection_index = 0
        self.highlightable_indices = []
        self.bonus_indices = []
        self.password = ''
        self.word_to_print = ''
        self.key_pressed = 0
        self.offset = 0
        self.cursor_x = 7
        self.cursor_y = 6

        stdscr = curses.initscr()
        curses.curs_set(False)
        stdscr.clear()
        stdscr.refresh()
        stdscr.nodelay(True)
        curses.start_color()
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_GREEN)
        stdscr.attron(curses.color_pair(1))
        self.make_new_dataset()

    def make_new_dataset(self):

        # Choose a new "memory" address to look at
        junk_chars = list(string.punctuation)
        self.address = random.randint(4096, 65500)
        self.selectable_text.clear()
        self.side_text.clear()

        # Test of side text
        for _ in range(self.side_text_size):
            self.side_text.append(' ')

        # Generate a new "memory" dump populated with junk
        for char in range(self.selectable_size):
            self.selectable_text.append(random.choice(junk_chars))

        # Generate a list of words with one password
        self.word_list = passwordgen.get_list_of_words(self.num_words,
                                                       self.word_length)
        random.shuffle(self.word_list)
        self.password = random.choice(self.word_list)
        # Keep track of where the password is for later bonus testing
        # It needs to be randomly placed, but we can't accidentally delete it
        # if a "dud replaced" bonus event occurs
        self.password_location = self.word_list.index(self.password)

        # Randomly insert the words and password among the junk chars,
        # but distribute somewhat evenly to prevent overlap
        self.max_spacing = (self.selectable_size-(self.word_length*self.num_words))//self.num_words
        self.offset = random.randint(1, self.max_spacing)

        for word in self.word_list:
            # Overwrite the junk chars with the words we want
            for char_idx, char in enumerate(list(word)):
                # Place the individual letters
                self.selectable_text[self.offset+char_idx] = word[char_idx]
                # Mark the start of all non-passwords
                if word is not self.word_list[self.password_location] and char_idx == 0:
                    self.word_start_locations.append(self.offset)
            self.offset = self.offset + self.word_length +\
                          random.randint(self.max_spacing-2, self.max_spacing)
            # Keep from placing words too near the end
            if self.offset > self.selectable_size:
                self.offset = self.selectable_size - self.word_length

    def update_cursor(self):

        if self.key_pressed == curses.KEY_DOWN or button_down.is_pressed:
            self.cursor_y = self.cursor_y + 1
        elif self.key_pressed == curses.KEY_UP or button_up.is_pressed:
            self.cursor_y = self.cursor_y - 1
        elif self.key_pressed == curses.KEY_RIGHT or button_right.is_pressed:
            self.cursor_x = self.cursor_x + 1
        elif self.key_pressed == curses.KEY_LEFT or button_left.is_pressed:
            self.cursor_x = self.cursor_x - 1

        # Constrain the position to selectable areas of the two columns
        if self.cursor_y < 6:
            self.cursor_y = 21
        elif self.cursor_y > 21:
            self.cursor_y = 6

        if self.cursor_x < 7:
            self.cursor_x = 38
        elif self.cursor_x == 26:  # Did we move left from the column on the right
            self.cursor_x = 18
        elif 18 < self.cursor_x < 27:
            self.cursor_x = 27
        elif self.cursor_x > 38:
            self.cursor_x = 7

        return self.cursor_y, self.cursor_x

    def get_cursor_pos_from_index(self, index):
        # Convert from a spot in selectable_text so
        # we can more easily modify the displayed characters

        self.index = index
        self.x_col = 7
        self.y_row = 6

        self.x_col = self.x_col + (self.index % 12)
        if self.index > 191:
            self.x_col = self.x_col + 20
            self.index = self.index - 192

        self.y_row = self.y_row + (self.index // 12)

        return [self.y_row, self.x_col]

    def get_index_from_cursor_pos(self, cur_y, cur_x):
        # Convert from a displayable cursor location
        # to a spot suitable for iterating through selectable_text

        self.selection_index = 0
        self.x_col = cur_x - 6
        self.y_row = cur_y - 6
        self.selection_characters = []
        self.end_of_word = 0

        if self.x_col > 18:
            self.selection_index = self.selection_index + 191 + (self.x_col - 20)
        else:
            self.selection_index = self.selection_index + self.x_col - 1

        self.selection_index = self.selection_index + (12 * self.y_row)

    def get_indices_of_selection(self):
        # Check for capital letters and open bracket characters
        # Now, look right of a letter in the list until a non letter is found

        self.highlightable_indices.clear()

        if self.selectable_text[self.selection_index].isupper():
            # At most, look right of a letter up to the current word length
            for len_offset, char in enumerate(range(self.word_length+1)):
                # Any junk character marks the end of the word
                if not self.selectable_text[self.selection_index + len_offset].isupper():
                    self.end_of_word = self.selection_index + len_offset
                    self.selection_characters = self.selectable_text[self.end_of_word-self.word_length:
                                                                     self.end_of_word]
                    for idx in range(self.end_of_word-self.word_length, self.end_of_word, 1):
                        self.highlightable_indices.append(idx)
                    break
            return ''.join(self.selection_characters)
        # Or, try and find a matching closing character
        elif self.selectable_text[self.selection_index] in ['(', '{', '[', '<']:
            # I could have iterated over a matching set of closing characters, but this is more readable to me
            if self.selectable_text[self.selection_index] == '(':
                self.closing_char = ')'
            elif self.selectable_text[self.selection_index] == '{':
                self.closing_char = '}'
            elif self.selectable_text[self.selection_index] == '[':
                self.closing_char = ']'
            elif self.selectable_text[self.selection_index] == '<':
                self.closing_char = '>'
            # Columns are 12 chars wide, so search up to that many spaces away within selectable text
            for len_offset, char in enumerate(range(13)):
                # Don't look past the end of the list
                if self.selection_index + len_offset > 383:
                    break
                # Record the indices of the enclosing brackets
                if  self.selectable_text[self.selection_index + len_offset] == self.closing_char:
                    self.end_of_word = self.selection_index + len_offset + 1
                    self.selection_characters = self.selectable_text[self.end_of_word-len_offset-1:
                                                                     self.end_of_word]
                    for idx in range(self.end_of_word-len_offset-1, self.end_of_word, 1):
                        self.highlightable_indices.append(idx)
                    return ''.join(self.selection_characters)
            self.highlightable_indices.append(self.selection_index)
            return self.selectable_text[self.selection_index]
        else: # Neither a letter or set of brackets found
            self.highlightable_indices.append(self.selection_index)
            return self.selectable_text[self.selection_index]

    def test_selection(self):

        self.likeness = 0
        self.entry_denied = False

        # Characters in a submission must match at the same index within a password
        if self.selectable_text[self.highlightable_indices[0]].isupper():
            for char_loc, idx in enumerate(self.highlightable_indices):
                if self.selectable_text[idx] == self.password[char_loc]:
                    self.likeness = self.likeness + 1
            # Only the password will have maximum likeness
            if self.likeness == self.word_length:
                self.logged_in = True
                sfx_good.play()
                trinket_trigger.on()
                return 'Password Accepted.'
            else:
                self.entry_denied = True
        # Apply bonus action if a matching set of brackets is found
        elif self.selectable_text[self.highlightable_indices[0]] in ['(', '{', '[', '<'] and \
            len(self.highlightable_indices) > 1 and \
            self.highlightable_indices[0] not in self.bonus_indices:
            # Randomly remove a dud word or reset attempts
            self.bonus_indices.append(self.highlightable_indices[0])
            if random.randint(0, 100) > 20:
                self.dud = random.choice(self.word_start_locations)
                self.word_start_locations.remove(self.dud)
                for idx in range(self.word_length):
                    self.selectable_text[self.dud+idx] = '.'
                sfx_dud.play()
                return 'Dud Removed.'
            else:
                self.attempts = 4
                sfx_reset.play()
                return 'Tries Reset.'
        # There's neither a penalty nor a bonus for clicking a valid bracket pair again
        elif self.highlightable_indices[0] in self.bonus_indices:
            return ''
        else: # Junk characters are automatically incorrect
            self.entry_denied = True

        if self.entry_denied:
            sfx_bad.play()
            if self.attempts > 1:
                self.attempts = self.attempts - 1
                return 'Entry denied.'
            else:
                self.locked_out = True
                return 'TERMINAL LOCKED' # PLEASE CONTACT ADMINISTRATOR

    def scroll_side_text(self, text_to_scroll):

        for col in range (14):
            self.side_text[0 + col] = ' '
        for row in range(14):
            # Copy the next row of characters onto the current row of characters
            self.side_text[row * 15:(row * 15) + 15] = \
                self.side_text[(row + 1) * 15: ((row + 1) * 15) + 15]
            # Clear the copied row since next row doesn't necessarily overwrite all spots
            self.side_text[(row + 1) * 15: ((row + 1) * 15) + 15] = '               '

        self.side_text[210] = '>'
        # Copy the player's entry separately as the last line
        for offset, letter in enumerate(list(text_to_scroll)):
            self.side_text[211 + offset] = letter

    def draw_terminal(self, stdscr):

        while self.key_pressed is not ord('q') or not button_quit.is_pressed:

            stdscr.clear()

            if not self.locked_out and not self.logged_in:

                self.update_cursor()
                self.get_index_from_cursor_pos(self.cursor_y, self.cursor_x)
                self.word_to_print = self.get_indices_of_selection()

                # Test Selection, pass, incorrect, bonus, or lockout
                # Also, "scroll" the printed side output up after testing
                if self.key_pressed == ord('e') or button_enter.is_pressed:
                    self.terminal_status = self.test_selection()
                    if self.terminal_status == 'Entry denied.':
                        self.scroll_side_text(self.word_to_print)
                        self.scroll_side_text(self.terminal_status)
                        self.scroll_side_text('Likeness='+str(self.likeness))
                    elif self.terminal_status == 'TERMINAL LOCKED' or \
                            self.terminal_status == 'Password Accepted.':
                        stdscr.nodelay(True)
                    elif self.terminal_status == 'Tries Reset.' or \
                            self.terminal_status == 'Dud Removed.':
                        self.scroll_side_text(self.word_to_print)
                        self.scroll_side_text(self.terminal_status)

                stdscr.addstr('Welcome to ROBCO Industries (TM) Termlink\n\n')
                stdscr.addstr('Password Required\n\n')
                stdscr.addstr('Attempts Remaining:')

                # Update attempts remaining after testing
                for attempt in range(self.attempts):
                    stdscr.addstr(u' \u2588'.encode(code))  # utf-8 FULL BLOCK █

                # Show the "memory" dump
                # With the selectable text wrapping in columns
                for row in range(self.rows):
                    stdscr.addstr(row + 6, 0, hex(self.address+(row * 12)).upper())
                    stdscr.addstr(row + 6, 7, ''.join(self.selectable_text[12 * row:(12 * row) + 12]))
                    stdscr.addstr(row + 6, 20, hex(self.address+row+16).upper())
                    stdscr.addstr(row + 6, 27,''.join(self.selectable_text[(12 * row) + 192:(12 * row) + 204]))

                # Highlight the appropriate characters
                for i, _ in enumerate(self.highlightable_indices):
                    self.y_row, self.x_col = self.get_cursor_pos_from_index(self.highlightable_indices[i])
                    stdscr.chgat(self.y_row, self.x_col, 1, curses.color_pair(2))

                # Show hidden location/password data for debugging
                #stdscr.addstr(1, 20, str(self.word_start_locations))
                #stdscr.addstr(1, 40, 'likeness=' + str(self.likeness))
                #stdscr.addstr(2, 40, self.password)
                #stdscr.addstr(3, 40, str(self.selection_index))
                #stdscr.addstr(4, 40, str(self.get_cursor_pos_from_index(self.selection_index)))
                #stdscr.addstr(5, 40, self.terminal_status)
                #stdscr.addstr(5, 40, str(self.highlightable_indices))
                #stdscr.addstr(5, 40, str(self.bonus_indices))

                # Draw the side text of scrolling entries
                for row in range(15):
                    stdscr.addstr(row + 6, 40, ''.join(self.side_text[15 * row:(15 * row) + 15]))

                stdscr.addstr(21, 40, '>' + self.word_to_print)
                # Adding the blink attribute cleared the color attribute, so we need to add it again
                # Multiple attributes for curses require a bitwise OR (go figure)
                stdscr.addch('█', curses.A_BLINK | curses.color_pair(1))


            elif self.locked_out:
                # Only allow system reboot
                stdscr.addstr(9, 22, self.terminal_status)
                stdscr.addstr(11, 16, 'PLEASE CONTACT ADMINISTRATOR')

            elif self.logged_in:
                # Allow "logging out" to reset the game
                stdscr.addstr('Welcome to ROBCO Industries (TM) Termlink')
                stdscr.addstr(21, 0, self.terminal_status)
                stdscr.addch('█', curses.A_BLINK | curses.color_pair(1))

            # Refresh the screen
            stdscr.refresh()
            self.button_idle = True
            curses.napms(170)
            # getch() is blocking, so the program waits for input
            #self.key_pressed = stdscr.getch()
            while self.button_idle:
                self.key_pressed = stdscr.getch()
                if self.key_pressed != -1:
                    self.button_idle = False
                for button in buttons:
                    if button.is_pressed:
                        self.button_idle = False
                    if button_quit.is_pressed:
                        curses.endwin()
                        sys.exit()
                curses.napms(30)
	    # Lock out or log in will set nodelay() to True, making getch non-blocking
            # but we want to immediately revert it to wait for input and not constantly draw the terminal
            #stdscr.nodelay(False)

    def main(self):
        # Cleanly handle setup and close of curses within the shell
        curses.wrapper(self.draw_terminal)


terminal = TerminalGame()

if __name__ == "__main__":

    terminal.main()
