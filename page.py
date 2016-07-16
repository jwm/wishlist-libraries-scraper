#!/usr/bin/env python
from __future__ import print_function

BEST_BRANCHES = {
    'Harvard': ['Lamont', 'Widener'],
    'MBLN': ['BPL - Central'],
    'Minuteman': ['CAMBRIDGE', 'INTERNET'],
}

import collections
import itertools
import json

wishlist_items = json.load(open('wishlist.json'))
library_availability = json.load(open('library.json'))

print('''
    <!DOCTYPE html>
    <html>
    <head>
            <title>jwm's Amazon Wishlist</title>

            <style type='text/css'>
                    li {
                            list-style-type: none;
                            width: 50%;
                    }

                    li.left {
                            float: left;
                            clear: left;
                    }
                    li.right {
                            float: right;
                            clear: right;
                    }

                    img {
                            border: 0;
                            margin-right: 0.3em;
                            margin-bottom: 0.5em;
                    }
            </style>
    </head>
''')

print('''
    <body>
        <ul>
''')

def sort_key(value):
    return [int(i) for i in value['sort_key'].split('/')]

class_iter = itertools.cycle(('left', 'right'))
for item in sorted(wishlist_items, key=lambda item: sort_key(item)):
    print('<li class="{}">'.format(next(class_iter)))

    print('<a href="{}">'.format(item['amazon_url']))
    if 'url' not in item['image']:
        # FIXME
        continue
    print('<img style="float: left" src="{}" height="{}" width="{}" alt="{}">'.format(
        item['image']['url'], item['image']['height'],
        item['image']['width'], item['image']['caption'].encode('utf-8')
    ))
    print('</a>')

    print('{}<br>'.format(item['title'].encode('utf-8')))
    print('{}<br>'.format(item['by'].encode('utf-8')))

    if item['amazon_prices']:
        if 'list' in item['amazon_prices']:
            # FIXME: ??
            print('List: ', item['amazon_prices']['list'], '<br>')
        print('New ({}): {}, Used ({}): {}<br>'.format(
            item['amazon_prices']['new_count'],
            item['amazon_prices'].get('new_lowest_price', '-'),
            item['amazon_prices']['used_count'],
            item['amazon_prices'].get('used_lowest_price', '-')))
    elif 'Kindle' in item.get('format', ''):
        print('(Kindle)<br>')

    # FIXME: isbn
    all_libraries_holdings = [
        holding
        for holding
         in library_availability
         if holding['item']['isbn'] == item['isbn'] and
            ('digital_url' in holding or
             'call_num' in holding)
    ]
    unique_libraries = set([holding['library'] for holding in all_libraries_holdings])

    for library in sorted(unique_libraries):
        holdings = [
            holding for holding in all_libraries_holdings if holding['library'] == library]

        branch_call_numbers_text = []

        best_branches = set([
            holding['branch']
            for holding
             in holdings
             if holding['branch'] in BEST_BRANCHES[library]
        ])
        if best_branches:
            best_branches_available = [
                holding
                for holding
                 in holdings
                 if holding['branch'] in best_branches and
                    holding.get('available')
            ]
            if not best_branches_available:
                best_branches_own = collections.Counter([
                    (holding['branch'],
                     holding.get('digital_url', holding['catalog_url']))
                    for holding
                     in holdings
                     if holding['branch'] in best_branches
                ])
                branch_call_numbers_text.append(
                    ', '.join([
                        '<a href="{}">{}</a>: 0/{}'.format(info[1], info[0], num_owned)
                        for info, num_owned
                         in best_branches_own.items()
                    ])
                )
                best_branches = (
                    set([
                        holding['branch']
                        for holding
                         in holdings
                         if holding.get('available')]) -
                    best_branches)
        else:
            # If this item isn't owned by any of our best branches,
            # fall back to listing all branches that own it.
            best_branches = set([
                holding['branch']
                for holding
                in holdings
                if holding.get('available')
            ])

        for best_branch in best_branches:
            branch_owns = [
                holding
                for holding
                 in holdings
                 if holding['branch'] == best_branch
            ]
            available_at_branch = [
                holding
                for holding
                 in branch_owns
                 if holding.get('available')
            ]
            available_call_numbers = collections.Counter([
                (holding['call_num'],
                 holding.get('digital_url', holding['catalog_url']))
                for holding
                 in available_at_branch
            ])

            format_str = u'{} ({}/{}){}'
            values = []
            if (best_branch == 'INTERNET' and branch_owns and
                    'digital_url' in branch_owns[0]):
                values.append('<a href="{}">{}</a>'.format(
                    branch_owns[0]['digital_url'], best_branch))
            else:
                values.append(best_branch)
            values.extend([len(available_at_branch), len(branch_owns)])
            if sum(available_call_numbers.values()):
                values.append(
                    u': ' + u', '.join([
                        u'{}<a href="{}">{}</a>'.format('{}@'.format(count) if count != len(available_at_branch) else '', info[1], info[0])
                        for info, count
                         in available_call_numbers.items()
                    ]))
            else:
                values.append('')
            branch_call_numbers_text.append(format_str.format(*values))

        library_owns = len(holdings)
        if library_owns == 0:
            continue

        library_available = len([
            holding
            for holding
             in holdings
             if holding.get('available')
        ])

        print('<strong>{}</strong>'.format(library), end='')
        if len(branch_call_numbers_text) != 1:
            print(': {}/{} available'.format(library_available, library_owns), end='')
        if branch_call_numbers_text:
            print(u': {}'.format(u', '.join(branch_call_numbers_text)).encode('utf-8'))
        print('<br>')

    print('</li>')

print('''
    </ul>
    </body>
    </html>
''')
