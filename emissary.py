#!/usr/bin/python3 
import operator, traceback, sys
from functools import reduce
from pprint import pprint
import argparse
try:
    import difflib
except:
    print("Could not import difflib. You will not get suggestions for misspelled item names.")
    
import numpy
numpy.seterr(invalid="ignore", # 0./0.
             divide="ignore")  #  x/0.
float64=numpy.float64
numpy.set_printoptions(precision=3) # for my numpy, this does not work on float64s outside arrays.


# local imports
import char
# stats for your character.
# note that you will manually have to run

import parsing
# parsing of actions/*.txt
# includes action class

import linear
def initialize():
    print("initializing...")
    global items, actions, cards, item2category, parser
    item2category= parsing.read_all_categories()
    cards={} # dict: card name to list of action names
    actions={} # dict: name to action object
#    parsing.action("Grind Echos",
#                   {"Penny":100*char.attributes["EPA"]})\
#           .register(actions)
#    parsing.action("Grind for %0.2f SPA"%char.attributes["SPA"],
#                   {"Hinterland Scrip":char.attributes["SPA"]})\
#           .register(actions)
    parsing.read_all_actions(actions=actions,
                     item2category=item2category,
                     cards=cards)
    items=parsing.items_from_actions(actions, cards, item2category)


def parse_args():
    parser=argparse.ArgumentParser(sys.argv[0],\
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-g", "--grind", metavar="'Hinterland Scrip'",
                        type=str, default=None,
                        help="Item to grind for. Acceptable options are 'Echo' or any other of --list-items.")
    parser.add_argument("-n", "--num", metavar="num",
                        type=float, default=1,
                        help="Number of items we have to grind.")
    parser.add_argument("-m", "--max", metavar="limit",
                        type=int, default='15',
                        help="Write out at most <limit> grinds")
    parser.add_argument("-c", "--cards", 
                        action='store_true',
                        help="Show the effect of cards on grind. (Note that searching for grinds with -C enabled is mostly a better alternative.)")
    parser.add_argument("-d", "--debug", 
                        action='store_true',
                        help="Print debug output.")
    parser.add_argument("-v", "--verbose", 
                        action='store_true',
                        help="Be verbose, print details about each grind.")
    parser.add_argument("-a", "--all", 
                        action='store_true',
                        help="For -c, even print cards which were not picked.")
    parser.add_argument("-f", "--favours", 
                        action='store_true',
                        help="Assume that we can indefinitely grind favours at one favour per action")
    parser.add_argument("-C", "--cards-available", 
                        action='store_true',
                        help="Assume that we can indefinitely draw any cards we need")
    parser.add_argument("-X", "--no-gift-cards", 
                        action='store_true',
                        help="Do *not* make the CtD and SiC cards freely available")
    parser.add_argument("-L", "--list-items", 
                        action='store_true',
                        help="List all items the program knows about")
    parser.add_argument("-A", "--grind-all-items", 
                        action='store_true',
                        help="Try to grind all items (except for internal ones like Card, Meta, Choice or -b)")

    parser.add_argument("-b", "--background", metavar="<item>",
                        type=str, default=None,
                        help="Assume you will also spend lots of actions grinding for <item>, so any action which gains <item> as a side effect will save you some actions. (try Penny or 'Hinterland Scrip'")

    return vars(parser.parse_args(sys.argv[1:]))


def single_item_dict(iname, num):
    if not iname in items and not args["grind"].startswith("Echo"):
            print("I do not know of any item '%s'. Did you mean any of: %s"\
                  %(iname, difflib.get_close_matches(iname, items)))
            exit(-1)
    return {iname:num}

def add_sources(d, args, quiet=False):
    def log(*args):
        if not quiet:
            print(*args)
    num_avail=100000 # no one item should need more than that many cards/favs to grind any item
    num_avail*=-1
    # negative because we modify the gains we want.
    # (negative gain requirement == algorithm may spend resource)
    if not args["no_gift_cards"]:
        d["Card: A Gift from the Capering Relicker"]=num_avail
        d["Card: Secrets and Spending"]=num_avail
    addcards=[]
    if args["cards_available"]:
        log("(We assume that any cards can be drawn indefinitely at will, including favour grinding cards like connected pets.)")
        addcards=cards.keys()
    elif args["favours"]:
        log("(We assume that favours are freely available for 1 action per favour.)")
        addcards= filter(lambda c:c.startswith("Meta: Favours:"), cards.keys())
    for c in addcards:
        cardname="Card: %s"%c
        d[cardname]=num_avail
    return d

if __name__=="__main__":
    args=parse_args()
    initialize()
    if args["list_items"]:
        print("Known items:\n")
        # TODO: sort by category etc
        for i in sorted(items.keys()):
            print(i)
        exit(0)

    background={}
    if args["background"]!=None:
        num_bg=100.0
        print("Calculating action cost per background item %s"%args["background"])
        res=linear.optimize(actions, items, min_gains=add_sources(single_item_dict(args["background"], num_bg), args, quiet=True))
        assert res.status==0, "Background item grind search failed!"
        background[args["background"]]=res.gross_action_cost/num_bg
        print("Will assume that the best grind for background item %s takes %0.4f actions per %s (%0.4f %s per action)"
              %(args["background"], res.gross_action_cost/num_bg, args["background"], num_bg/res.gross_action_cost, args["background"]))

    if args["grind_all_items"]:
        assert not args["cards"], "Bad mix of options"
        assert not args["grind"], "Bad mix of options"
        min_gains=add_sources({}, args)
        actioncosts=dict(background)
        num=args["num"]
        for i in sorted(items.keys()):
            if i.startswith("Favours:") or i.startswith("Meta:") or i==args["background"] \
               or (i in ["Echo", "Penny"] and args["background"] in  ["Echo", "Penny"]) \
               or i.startswith("Choice:") or i.startswith("Card:"):
                continue
            print(i)
            assert not i in min_gains, "%s is already in min_gains"%i
            min_gains[i]=num
            acost,action=linear.best_grinds(actions, items, min_gains=min_gains, num_grinds=1,
                                     debug=args["debug"], verbose=args["verbose"], background=background)
            if acost!=None:
                acost/=num
            actioncosts[i]=acost
            del min_gains[i]
        f=open("_gen_actioncosts.py", "w")
        f.write("# generated by %s, do not edit\n"%" ".join(sys.argv))
        f.write("# (see exact call for infos on background and card inclusion settings.)\n")
        f.write("actioncosts=%s\n"%actioncosts)
        f.close()
        print("results were written to _gen_actioncosts.py")
        exit(0)
    
    min_gains=add_sources(single_item_dict(args["grind"], args["num"]), args)
    if args["cards"]:
        linear.best_card_grinds(actions, items, cards, min_gains, debug=args["debug"], verbose=args["verbose"], print_all=args["all"], favours=args["favours"], background=background)
    elif args["grind"]:
        linear.best_grinds(actions, items, min_gains=min_gains, num_grinds=args["max"], max_actions=None, debug=args["debug"], verbose=args["verbose"], background=background)
    #for min_gains in [{"Penny":5000}, {"Human Arm":1,"Penny":5000}]:
    #    linear.run(actions, itemdict, min_gains=min_gains)
    #blocked_items, allow_cards