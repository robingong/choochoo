
from glob import glob
from os import stat
from os.path import isdir, join

from sqlalchemy.orm.exc import NoResultFound
from urwid import Edit, Pile, Columns, connect_signal

from .utils import datetime_to_epoch
from .args import PATH, ACTIVITY, EDIT_ACTIVITIES, FORCE
from .fit.format.read import filtered_records
from .lib.io import tui
from .squeal.database import Database
from .squeal.tables.activity import Activity, FileScan, ActivityDiary, ActivityTimespan, ActivityWaypoint
from .uweird.editor import EditorApp
from .uweird.factory import Factory
from .uweird.focus import MessageBar, FocusWrap
from .uweird.widgets import SquareButton, ColSpace


class ActivityWidget(FocusWrap):

    def __init__(self, log, tabs, bar, outer):
        self.__outer = outer
        factory = Factory(tabs=tabs, bar=bar)
        self.title = factory(Edit(caption='Title: '))
        self.sort = factory(Edit(caption='Sort: '))
        self.delete = SquareButton('Delete')
        delete = factory(self.delete, message='delete from database')
        self.reset = SquareButton('Reset')
        reset = factory(self.reset, message='reset from database')
        self.description = factory(Edit(caption='Description: ', multiline=True))
        super().__init__(
            Pile([self.title,
                  Columns([(20, self.sort),
                           ColSpace(),
                           (10, delete),
                           (9, reset)
                           ]),
                  self.description,
                  ]))

    def connect(self, binder):
        connect_signal(self.reset, 'click', lambda widget: binder.reset())
        connect_signal(self.delete, 'click', lambda widget: self.__on_delete(widget, binder))

    def __on_delete(self, _unused_widget, binder):
        binder.delete()
        self.__outer.remove(self)


@tui
def edit_activities(args, log):
    '''
# edit-activities

    ch2 edit-activities

The interactive editor for activities.  Allows addition, deletion and modification of activities.

Once added, activities can be imported and will appear in the diary.

To exit, alt-q (or, without saving, Alt-x).
    '''
    session = Database(args, log).session()
    EditorApp(log, session, MessageBar(), "Activities", ActivityWidget, Activity).run()


def add_file(log, session, activity, path, force):
    if force:
        session.query(ActivityDiary).filter(ActivityDiary.fit_file == path).delete()
    data, types, messages, records = filtered_records(log, path)
    diary = ActivityDiary(activity=activity, fit_file=path)
    session.add(diary)
    timespan = None
    for record in records:
        record = record.force()
        if record.name == 'event' and not diary.start:
            diary.start = record.value.timestamp
            diary.date = record.value.timestamp
        if record.name == 'event' and record.value.event_type == 'start':
            timespan = ActivityTimespan(activity_diary=diary,
                                        start=datetime_to_epoch(record.value.timestamp))
            session.add(timespan)
        if record.name == 'record':
            waypoint = ActivityWaypoint(activity_diary=diary,
                                        epoch=datetime_to_epoch(record.value.timestamp),
                                        latitude=record.value.position_lat,
                                        longitude=record.value.position_long,
                                        hr_bpm=record.none.heart_rate,
                                        distance=record.value.distance,
                                        speed=record.value.enhanced_speed)
            session.add(waypoint)
        if record.name == 'event' and record.value.event_type == 'stop_all':
            timespan.finish = datetime_to_epoch(record.value.timestamp)
            diary.finish = record.value.timestamp


def add_stats(log, session, activity_id, path):
    pass


def add_activity(args, log):
    '''
# add-activity

    ch2 add-activity ACTIVITY PATH

Read one or more (if PATH is a directory) FIT files and associated them with the given activity type.
    '''
    db = Database(args, log)
    force = args[FORCE]
    activity = args[ACTIVITY][0]
    with db.session_context() as session:
        try:
            activity = session.query(Activity).filter(Activity.title == activity).one()
        except NoResultFound:
            if force:
                activity = Activity(title=activity)
                session.add(activity)
            else:
                raise Exception('Activity "%s" is not defined - see ch2 %s' % (activity, EDIT_ACTIVITIES))

    path = args.path(PATH, index=0, rooted=False)
    if isdir(path):
        path = join(path, '*.fit')
    files = list(glob(path))
    if not files:
        raise Exception('No match for "%s"' % path)
    for file in files:
        with db.session_context() as session:
            try:
                scan = session.query(FileScan).filter(FileScan.path == file).one()
            except NoResultFound:
                scan = FileScan(path=file, last_scan=0)
                session.add(scan)
            last_modified = stat(file).st_mtime
            if force or last_modified > scan.last_scan:
                log.info('Scanning %s' % file)
                add_file(log, session, activity, file, force)
                add_stats(log, session, activity, file)
                scan.last_scan = last_modified
                session.flush()
            else:
                log.debug('Skipping %s (already scanned)' % file)
                session.expunge(scan)