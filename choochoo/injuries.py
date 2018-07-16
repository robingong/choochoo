
from urwid import WEIGHT, Edit, Pile, Columns, connect_signal, Padding, Text, Divider

from .log import make_log
from .squeal.binders import Binder
from .squeal.database import Database
from .squeal.injury import Injury
from .uweird.calendar import TextDate
from .uweird.factory import Factory
from .uweird.fixed import Fixed
from .uweird.focus import MessageBar, FocusWrap
from .uweird.tabs import TabList
from .uweird.widgets import DividedPile, Nullable, SquareButton, ColSpace, ColText, DynamicContent
from .widgets import App


class InjuryWidget(FocusWrap):

    def __init__(self, log, tabs, bar):

        factory = Factory(tabs=tabs, bar=bar)
        self.title = factory(Edit(caption='Title: '))
        self.start = factory(Nullable('Open', lambda date: TextDate(log, bar=bar), bar=bar))
        self.finish = factory(Nullable('Open', lambda date: TextDate(log, bar=bar), bar=bar))
        self.sort = factory(Edit(caption='Sort: '))
        self.__raw_reset = SquareButton('Reset')
        reset = factory(self.__raw_reset, message='reset from database')
        self.description = factory(Edit(caption='Description: ', multiline=True))
        super().__init__(
            Pile([self.title,
                  Columns([(18, self.start),
                           ColText(' to '),
                           (18, self.finish),
                           ColSpace(),
                           (WEIGHT, 3, self.sort),
                           ColSpace(),
                           (9, reset)
                           ]),
                  self.description,
                  ]))

    def connect(self, binder):
        connect_signal(self.__raw_reset, 'click', lambda widget: binder.refresh())


class Injuries(DynamicContent):

    # we have to be careful to work well with qlalchemy's session semantics.
    # to do this:
    # - general editing is done within a single session
    # - this includes reset, delete and adding empty new values
    #   (all can be done without session commit)
    # - to do this, we must keep a store of the windgets / binders
    #   so that we don't need to query (after initial loading)
    # - data are saved / discarded on final exit (only)

    def _make(self):
        tabs = TabList()
        body = []
        for injury in self._session.query(Injury).order_by(Injury.sort).all():
            widget = InjuryWidget(self._log, tabs, self._bar)
            widget.connect(Binder(self._log, self._session, widget, Injury, defaults={'id': injury.id}))
            body.append(widget)
        # and a button to add blanks
        more = SquareButton('More')
        body.append(tabs.append(Padding(Fixed(more, 8), width='clip')))
        connect_signal(more, 'click', self.__add_blank)
        return DividedPile(body), tabs

    def __add_blank(self, _unused_widget):
        tabs = TabList()
        widget = InjuryWidget(self._log, tabs, self._bar)
        widget.connect(Binder(self._log, self._session, widget, Injury))
        body = self._w.contents
        n = len(body)
        body.insert(n-1, (Divider(), (WEIGHT, 1)))
        body.insert(n-1, (widget, (WEIGHT, 1)))
        self._w.contents = body
        n = len(self)
        self.insert_all(n-1, tabs)


class InjuryApp(App):

    def __init__(self, log, session, bar):
        self.__session = session
        tabs = TabList()
        self.injuries = tabs.append(Injuries(log, session, bar))
        super().__init__(log, 'Diary', bar, self.injuries, tabs, session)

    def rebuild(self, _unused_widget, _unused_value):
        self.__session.commit()
        self.injuries.rebuild()
        self.root.discover()


def main(args):
    log = make_log(args)
    session = Database(args, log).session()
    InjuryApp(log, session, MessageBar()).run()