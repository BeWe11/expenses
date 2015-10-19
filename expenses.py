#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import argparse
from decimal import Decimal, InvalidOperation
from datetime import datetime
from pydblite import Base


today = datetime.today()
date_format = '%d.%m.%Y'

homefolder = os.path.expanduser('~')
db_file_name = '.expenses.pdl'
path = os.path.join(homefolder, db_file_name)
db = Base(path)


def entry_string(entry):
    name = entry['name']
    cost = '{:.2f}'.format(entry['cost'])
    id = entry['__id__']
    date = datetime.strftime(entry['date'], date_format)
    tags = ', '.join(entry['tags'])
    result = '{:<20} {:<10} {:<12} {:<6} {:<60}'.format(name, cost, date, id, tags)
    return result


def add_entry(args):
    if args.date:
        try:
            date = datetime.strptime(args.date, date_format)
        except ValueError:
            raise ValueError('Incorrect date format, should be "DD.MM.YYYY".')
    else:
        date = today

    if args.tags:
        tags = args.tags
    else:
        tags = []

    db.insert(name=args.name, cost=Decimal(args.cost), date=date, tags=tags)
    db.commit()


def delete_entry(args):
    while 1:
        confirm = input('Do you really want to delete entry {}? (y/n) '.format(args.id))
        if confirm in ['y', 'n']:
            break

    if confirm == 'y':
        try:
            del db[args.id]
        except KeyError:
            raise KeyError('There is no entry with ID {}.'.format(args.id))
        db.commit()
        print('Deleted entry {}!'.format(args.id))


def change_entry(args):
    if args.col != 'tags':
        assert len(args.val) == 1, 'Only one value for column "{}" possible.'.format(args.col)

    if args.col == 'name':
        val = args.val[0]
    elif args.col == 'cost':
        try:
            val = Decimal(args.val[0])
        except InvalidOperation:
            raise InvalidOperation('Cannot convert "{}" to decimal.'.format(args.val[0]))
    elif args.col == 'date':
        try:
            val = datetime.strptime(args.val[0], date_format)
        except ValueError:
            raise ValueError('Incorrect date format, should be "DD.MM.YYYY".')
    elif args.col == 'tags':
        val = args.val

    db.update(db[args.id], **{args.col: val})
    db.commit()


def list_entries(args):
    print('')
    print('{:<20} {:<10} {:<12} {:<6} {:<20}'.format('Name', 'Cost[Euro]', 'Date', 'ID', 'Tags'))
    print('- ' * 33 + '-')

    if args.days:
        days = args.days
    else:
        days = 30

    total_cost = 0
    for entry in sorted([entry for entry in db if (today-entry['date']).days <= days], key=lambda x: x['date']):
        if args.tags and not any(tag in entry['tags'] + [entry['name']] for tag in args.tags):
            continue
        if args.Tags and any(tag in entry['tags'] + [entry['name']] for tag in args.Tags):
            continue
        total_cost += entry['cost']
        print(entry_string(entry))

    print('- ' * 33 + '-')
    print('Total cost: {:.2f} Euro'.format(total_cost))
    print('')


def setup(args):
    if os.path.isfile(path):
        backup_path = path + '.bak'
        shutil.copy(path, backup_path)

    if args.overwrite:
        mode = 'override'
    else:
        mode = 'open'

    db = Base(path)

    if args.overwrite:
        db.create('name', 'cost', 'date', 'tags', mode=mode)
        print('Data base in {} has been overwritten!'.format(path))
    else:
        if db.exists():
            print('{} already exists and is a database. If you want to recreate'
                  ' it, use the -o flag.'.format(path))
        else:
            db.create('name', 'cost', 'date', 'tags', mode=mode)
            print('Created database at {}!'.format(path))


def main():
    parser = argparse.ArgumentParser(prog='expenses', description='This script'
        ' manages your expenses.')
    subparsers = parser.add_subparsers(dest='subparser_name')

    parser_add = subparsers.add_parser('add', help='Add an entry to the data'
        ' base.')
    parser_add.add_argument('name', type=str, help='Name of the entry.')
    parser_add.add_argument('cost', type=str, help='Cost of the entry.')
    parser_add.add_argument('-d', '--date', type=str, help='Date of'
            ' expenditure. Usage "-d DD.MM.YYYY". Defaults to the current date.')
    parser_add.add_argument('-t', '--tags', type=str, nargs='+', help='Give a'
        ' list of tags that the entry should be associated with. Any string'
        ' can be a tag, you should use the same strings for things you want to'
        ' group. Usage: "-t tag1 tag2 ...".')
    parser_add.set_defaults(func=add_entry)

    parser_delete = subparsers.add_parser('delete', help='Delete an entry from'
        ' the database.')
    parser_delete.add_argument('id', type=int, help='ID of the entry to be'
        ' deleted.')
    parser_delete.set_defaults(func=delete_entry)

    parser_change = subparsers.add_parser('change', help='Change an entry in'
        ' the database.')
    parser_change.add_argument('id', type=int, help='ID of the entry to be'
        ' changed.')
    parser_change.add_argument('col', type=str, help='Column to be changed. Valid choices are'
        ' "name", "cost", "date" and "tags".')
    parser_change.add_argument('val', type=str, nargs='*', help='Value to be'
        ' inserted. The tags list will get replaced completely.')
    parser_change.set_defaults(func=change_entry)

    parser_list = subparsers.add_parser('list', help='List entries.')
    parser_list.add_argument('-d', '--days', type=int, help='Number of past'
        ' days the will be included in the output. Defaults to 30.')
    parser_list.add_argument('-t', '--tags', type=str, nargs='+', help='Only'
        ' list entries with the specified tags. Entry names are treated as'
        ' tags. Usage: "-t tag1 tag2 ...".')
    parser_list.add_argument('-T', '--Tags', type=str, nargs='+', help='Only'
        ' list entries without the specified tags. Entry names are treated as'
        ' tags. Usage: "-T tag1 tag2 ...".')
    parser_list.set_defaults(func=list_entries)

    parser_setup = subparsers.add_parser('setup', help='Create the database in'
        ' "~/.expenses.pdl". If the file already exists, a backup will be'
        ' created at "~/.expenses.pdl.bak".')
    parser_setup.set_defaults(func=setup)
    parser_setup.add_argument('-o', '--overwrite', action='store_true',
        help='If given, overwrites the data base if it exists already.')

    args = parser.parse_args()

    if not db.exists() and args.subparser_name != 'setup':
        if os.path.isfile(path):
            raise IOError('{} exists, but is not a database. Run "expenses setup".'.format(path))
        else:
            raise IOError('{} does not exist. Run "expenses setup".'.format(path))

    if args.subparser_name != 'setup':
        db.open()
    args.func(args)


if __name__ == "__main__":
    main()
