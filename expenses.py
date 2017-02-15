#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import argparse
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta
from pydblite import Base

import numpy as np
from matplotlib import pyplot as plt
plt.rc('text', usetex=True)
plt.rc('axes', labelsize=16)


today = datetime.today()
days_per_month = 30
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
            if args.date.isdigit():
                date = today - timedelta(days=int(args.date))
            else:
                raise ValueError('Incorrect date format, should be'
                                 ' "DD.MM.YYYY" or a positive integer.')
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

    assert args.col in ['name', 'cost', 'date', 'tags'], 'Valid column choices' \
    ' are "name", "cost", "date" and "tags".'

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

    if args.sort:
        assert args.sort in ['name', 'cost', 'date'], 'Valid column' \
        'choices are "name", "cost" and "date".'
        sort_key = args.sort
    else:
        sort_key = 'date'

    include_tags = []
    exclude_tags = []
    if args.tags:
        for tag in args.tags:
            if tag.startswith('/'):
                exclude_tags.append(tag.lstrip('/'))
            else:
                include_tags.append(tag)

    total_cost = 0
    for entry in sorted([entry for entry in db if (today-entry['date']).days <= days], key=lambda x: x[sort_key]):
        if include_tags and not any(tag in entry['tags'] + [entry['name']] for tag in include_tags):
            continue
        if exclude_tags and any(tag in entry['tags'] + [entry['name']] for tag in exclude_tags):
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

    db = Base(path)

    if args.overwrite:
        while 1:
            confirm = input('Do you really want to overwrite the database ? (y/n) ')
            if confirm in ['y', 'n']:
                break
        if confirm == 'y':
            db.create('name', 'cost', 'date', 'tags', mode='override')
            print('Data base in {} has been overwritten!'.format(path))
    else:
        if db.exists():
            print('{} already exists and is a database. If you want to recreate'
                  ' it, use the -o flag.'.format(path))
        else:
            db.create('name', 'cost', 'date', 'tags', mode='open')
            print('Created database at {}!'.format(path))


def plot_average(args):
    if args.days:
        days = args.days
    else:
        days = (today - db[0]['date']).days - days_per_month

    include_tags = []
    exclude_tags = []
    if args.tags:
        for tag in args.tags:
            if tag.startswith('/'):
                exclude_tags.append(tag.lstrip('/'))
            else:
                include_tags.append(tag)

    average_costs = []

    for current_day in range(days):
        if not include_tags:
            include_tags = ["all"]
        total_cost = {tag: 0 for tag in include_tags}

        for entry in sorted([entry for entry in db if (
                current_day <= (today-entry['date']).days <= days_per_month + current_day)], key=lambda x: x['date']
            ):
            if exclude_tags and any(tag in entry['tags'] + [entry['name']] for tag in exclude_tags):
                continue
            for tag in include_tags:
                if tag == "all" or tag in entry['tags'] + [entry['name']]:
                    total_cost[tag] += entry['cost']
        average_costs.append(total_cost)

    fig, ax = plt.subplots()
    ax.set_xlabel("Number of days before today")
    ax.set_xlim(days-1, 0)
    ax.set_ylabel("Expenses in the last 30 days")

    x = np.arange(0, len(average_costs))

    if args.combine:
        y = [sum([float(val[tag]) for tag in include_tags]) for val in average_costs]

        params = np.polyfit(x, y, args.order)
        fit = np.poly1d(params)
        z = fit(x)

        data_label = "Data with tags: " + ', '.join(include_tags)

        ax.plot(x, y, label=data_label)
        ax.plot(x, z, linestyle="--", color="g")
    else:
        for tag in include_tags:
            y = [float(val[tag]) for val in average_costs]

            params = np.polyfit(x, y, args.order)
            fit = np.poly1d(params)
            z = fit(x)

            data_label = "Data with tag: " + str(tag)

            ax.plot(x, y, label=data_label)
            ax.plot(x, z, linestyle="--", color="g")

    if args.order == 1:
        fit_label = r"$%d^{st}$ order fits" % args.order
    elif args.order == 2:
        fit_label = r"$%d^{nd}$ order fits" % args.order
    else:
        fit_label = r"$%d^{th}$ order fits" % args.order
    ax.plot([0], [0], linestyle="--", color="g", label=fit_label)

    ax.legend(loc='best')
    plt.show()


def compare(args):
    if args.days:
        days = args.days
    else:
        days = 30

    include_tags = []
    exclude_tags = []
    if args.tags:
        for tag in args.tags:
            if tag.startswith('/'):
                exclude_tags.append(tag.lstrip('/'))
            else:
                include_tags.append(tag)

    assert len(include_tags) > 0, "At least one tag has to be given!"

    days_per_month = 30
    average_costs = []

    total_cost = {tag: 0 for tag in include_tags}
    for entry in sorted([entry for entry in db if (
            0 <= (today-entry['date']).days <= days)], key=lambda x: x['date']
        ):
        if exclude_tags and any(tag in entry['tags'] + [entry['name']] for tag in exclude_tags):
            continue
        for tag in include_tags:
            if tag in entry['tags'] + [entry['name']]:
                total_cost[tag] += entry['cost']


    x = np.arange(0, len(include_tags))
    y = [total_cost[tag] for tag in include_tags]

    width = 0.85

    fig, ax = plt.subplots()
    ax.set_xticks(x + 0.5*width)
    ax.set_xticklabels(include_tags)
    ax.set_ylabel("Expenses")

    ax.bar(x, y, width)
    plt.show()


def main():
    parser = argparse.ArgumentParser(prog='expenses', description='This script'
        ' manages your expenses.')
    subparsers = parser.add_subparsers(dest='subparser_name')

    parser_add = subparsers.add_parser('add', help='Add an entry to the data'
        ' base.')
    parser_add.add_argument('name', type=str, help='Name of the entry.')
    parser_add.add_argument('cost', type=str, help='Cost of the entry.')
    parser_add.add_argument('-d', '--date', type=str, help='Date of'
            ' expenditure. Usage "-d DD.MM.YYYY". Alternatively accepts a'
            ' positive integer which amounts to the number of days which have'
            ' passed since the expenditure. Defaults to the current date.')
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
    parser_change.add_argument('col', type=str, help='Column to be changed.'
        ' Valid choices are "name", "cost", "date" and "tags".')
    parser_change.add_argument('val', type=str, nargs='*', help='Value to be'
        ' inserted. The tags list will get replaced completely.')
    parser_change.set_defaults(func=change_entry)

    parser_list = subparsers.add_parser('list', help='List entries.')
    parser_list.add_argument('-d', '--days', type=int, help='Number of past'
        ' days the will be included in the output. Defaults to 30.')
    parser_list.add_argument('-t', '--tags', type=str, nargs='+', help='Only'
        ' list entries with the specified tags. Entry names are treated as'
        ' tags. Usage: "-t tag1 tag2 ...". To exclude a tag, write "/tag".')
    parser_list.add_argument('-s', '--sort', type=str, help='Sort entries by'
        ' the given column name. Valid names are "name", "cost" and "date".')
    parser_list.set_defaults(func=list_entries)

    parser_plot_average = subparsers.add_parser('average', help='Plot average monthly spending.')
    parser_plot_average.add_argument('-d', '--days', type=int, help='Number of past'
        ' days the will be included in the output. If not given, every entry in the data base will be included.')
    parser_plot_average.add_argument('-t', '--tags', type=str, nargs='+', help='Only'
        ' include entries with the specified tags. Entry names are treated as'
        ' tags. Usage: "-t tag1 tag2 ...". To exclude a tag, write "/tag".')
    parser_plot_average.add_argument('-o', '--order', type=int, default=5, help='Order of the fit polynomial. Defaults to 5.')
    parser_plot_average.add_argument('-c', '--combine', action="store_true", help='When set to true, the values of all given tags will be summed up.')
    parser_plot_average.set_defaults(func=plot_average)

    parser_compare = subparsers.add_parser('compare', help='Compare monthly expenses of different categories.')
    parser_compare.add_argument('-d', '--days', type=int, help='Number of past'
        ' days the will be included in the output. Defaults to 30.')
    parser_compare.add_argument('-t', '--tags', type=str, nargs='+', help='Tags'
        'to compare. Usage: "-t tag1 tag2 ...". To exclude a tag, write "/tag".')
    parser_compare.set_defaults(func=compare)

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
