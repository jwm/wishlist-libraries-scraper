#!/usr/bin/env python

PREFERRED_BRANCHES = {
    'MBLN': ['BPL - Central', 'INTERNET'],
    'Minuteman': ['CAMBRIDGE', 'INTERNET'],
}

import itertools
import json

from jinja2 import Environment, FileSystemLoader, StrictUndefined


def get_holdings(all_holdings, isbn, library=None, branches=None):
    holdings = [
        holding
        for holding
        in all_holdings
        if holding['item']['isbn'] == isbn and
            ('digital_url' in holding or
             'call_num' in holding)
    ]

    if library:
        holdings = [holding for holding in holdings if holding['library'] == library]
    if branches:
        holdings = [holding for holding in holdings if holding['branch'] in branches]

    return holdings


def get_best_branches(holdings, library):
    preferred_branches_holdings = get_holdings(
        holdings, holdings[0]['item']['isbn'],
        library=library, branches=PREFERRED_BRANCHES[library]
    )

    if not preferred_branches_holdings:
        # If this item isn't owned by any of our preferred branches,
        # fall back to listing all branches that have it available.
        return sorted(set([
            holding['branch']
            for holding
            in holdings
            if holding.get('available') and
               holding['library'] == library
        ]), key=lambda branch: int(branch in PREFERRED_BRANCHES[library]), reverse=True)

    preferred_branches_available = set([
        holding['branch']
        for holding
        in preferred_branches_holdings
        if holding.get('available')
    ])
    if preferred_branches_available:
        return set([
            holding['branch']
            for holding
            in preferred_branches_holdings
        ])

    return sorted(set([
        holding['branch']
        for holding
        in holdings
        if (holding['library'] == library and
            holding.get('available')) or
           holding['branch'] in PREFERRED_BRANCHES[library]
    ]), key=lambda branch: int(branch in PREFERRED_BRANCHES[library]), reverse=True)


def sort_key(value):
    return [int(i) for i in value['sort_key'].split('/')]


wishlist_items = json.load(open('wishlist.json'))
library_availability = [
    item
    for item
    in json.load(open('library.json'))
    if 'isbn' in item['item']
]

template_data = {
    'items': [],
}

for item in sorted(wishlist_items, key=lambda item: sort_key(item)):
    item['holdings'] = get_holdings(library_availability, item['isbn'])
    if item['holdings']:
        item['display_branches'] = set(
            itertools.chain(*[
                get_best_branches(item['holdings'], library)
                for library
                in PREFERRED_BRANCHES
            ])
        )

    template_data['items'].append(item)

loader = FileSystemLoader(searchpath='templates')
env = Environment(loader=loader, undefined=StrictUndefined)
template = env.get_template('main.html')
print(template.render(template_data))
