from _csv import reader
from glob import glob
from itertools import zip_longest
from logging import getLogger, basicConfig, DEBUG
from os.path import splitext, basename, split, join
from sys import stdout
from tempfile import TemporaryDirectory

from choochoo.args import FIELDS
from choochoo.fit.format.records import no_names, append_units, no_bad_values, fix_degrees, chain
from choochoo.fit.format.tokens import filtered_records
from choochoo.fit.profile.fields import DynamicField
from choochoo.fit.profile.profile import read_profile
from choochoo.fit.summary import summarize, summarize_csv


def test_profile():

    basicConfig(stream=stdout, level=DEBUG)
    log = getLogger()
    nlog, types, messages = read_profile(log, '/home/andrew/project/ch2/choochoo/data/sdk/Profile.xlsx')

    cen = types.profile_to_type('carry_exercise_name')
    assert cen.profile_to_internal('farmers_walk') == 1

    session = messages.profile_to_message('session')
    field = session.profile_to_field('total_cycles')
    assert isinstance(field, DynamicField), type(field)
    for name in field.references:
        assert name == 'sport'

    workout_step = messages.profile_to_message('workout_step')
    field = workout_step.number_to_field(4)
    assert field.name == 'target_value', field.name
    fields = ','.join(sorted(field.references))
    assert fields == 'duration_type,target_type', fields


def test_decode():

    basicConfig(stream=stdout, level=DEBUG)
    log = getLogger()
    for record in filtered_records(log, '/home/andrew/project/ch2/choochoo/data/test/personal/2018-07-26-rec.fit',
                                   profile_path='/home/andrew/project/ch2/choochoo/data/sdk/Profile.xlsx'):
        print(record.into(tuple, filter=chain(no_names, append_units, no_bad_values, fix_degrees)))


def test_dump():

    basicConfig(stream=stdout, level=DEBUG)
    log = getLogger()
    summarize(log, FIELDS,
              '/home/andrew/project/ch2/choochoo/data/test/personal/2018-07-30-rec.fit',
              profile_path='/home/andrew/project/ch2/choochoo/data/sdk/Profile.xlsx')


def test_developer():

    basicConfig(stream=stdout, level=DEBUG)
    log = getLogger()
    summarize(log, FIELDS,
              '/home/andrew/project/ch2/choochoo/data/test/sdk/DeveloperData.fit',
              profile_path='/home/andrew/project/ch2/choochoo/data/sdk/Profile.xlsx')


def dump_csv(log, fit_file, csv_file):
    with open(csv_file, 'w') as output:
        summarize_csv(log, fit_file, out=output)


# https://docs.python.org/3/library/itertools.html#itertools-recipes
def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)


def compare_rows(us, them, name):
    assert us[0:3] == them[0:3], "%s != %s for %s" % (us[0:3], them[0:3], name)
    # after first 3 entries need to sort to be sure order is correct
    for us, them in zip(sorted(grouper(us[3:], 3)), sorted(grouper(them[3:], 3))):
        assert us == them, "%s != %s for %s" % (us, them, name)


def compare_csv(us, them, name):
    with open(us, 'r') as us_in, open(them, 'r') as them_in:
        us_reader = reader(us_in)
        them_reader = reader(them_in)
        next(them_reader)  # skip titles
        for us_row, them_row in zip(us_reader, them_reader):
            compare_rows(us_row, them_row, name)


def test_csv():

    basicConfig(stream=stdout, level=DEBUG)
    log = getLogger()

    with TemporaryDirectory() as dir:
        for fit_file in glob('/home/andrew/project/ch2/choochoo/data/test/sdk/*.fit'):
            fit_dir, file = split(fit_file)
            name = splitext(file)[0]
            csv_name = '%s.%s' % (name, 'csv')
            csv_us = join(dir, csv_name)
            csv_them = join(fit_dir, csv_name)
            dump_csv(log, fit_file, csv_us)
            compare_csv(csv_us, csv_them, name)
