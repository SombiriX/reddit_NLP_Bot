'''
This program pulls comments from reddit for further analysis using natural language processing
Author Sombiri Enwemeka
'''
import sys
import os
import watson_developer_cloud
import watson_developer_cloud.natural_language_understanding.features.v1 as features
import praw
import json
import argparse
from unicodedata import normalize
sys.path.append(os.path.join(os.getcwd(), '..'))


def get_watson_nlu(username, password):
    if (username is None or password is None or
            username is "" or password is ""):
        return None
    watson_nlu = {
        "url": "https://gateway.watsonplatform.net/natural-language-understanding/api",
        "username": username,
        "password": password}
    return watson_developer_cloud.NaturalLanguageUnderstandingV1(
        version='2017-02-27',
        username=watson_nlu["username"],
        password=watson_nlu["password"])


def norm(text):
    if text is None:
        return None
    return normalize('NFKD', text).encode('ascii', 'ignore')


def test_redditor(submission):
    if submission is None:
        return None
    if submission.author is None:
        return None
    return norm(submission.author.name)


def main():
    '''
    Main script execution
    '''

    comment_data = {}
    f = None

    parser = argparse.ArgumentParser(description='Analyze reddit comments')
    parser.add_argument('-r', action='store_true', help='refresh site data')
    parser.add_argument('--subreddit', default='the_donald', help='Subreddit to examine')
    parser.add_argument('-n', default=5, help='Number of posts to examine')
    parser.add_argument('-o', default='commentData.json', help='Output file name')
    parser.add_argument('-k', default='../apiKeys.json', help='Path to API keys file')

    args = parser.parse_args()

    # Check whether to update comment data
    if args.r:
        api_keys = None
        try:
            with open(args.k, 'r') as fp:
                api_keys = json.load(fp)
        except IOError as oops:
            print oops
            exit()

        # Get all comment text from top n subreddit posts
        reddit = praw.Reddit(
            client_id=api_keys['reddit'][0],
            client_secret=api_keys['reddit'][1],
            user_agent=api_keys['reddit'][2])
        subreddit = reddit.subreddit(args.subreddit)

        nlu = get_watson_nlu(api_keys['watson'][0], api_keys['watson'][1])

        # Put the reddit data into a dictionary
        for submission in subreddit.top(time_filter='all', limit=args.n):
            submission.comments.replace_more(limit=0)
            comment_data[submission.id] = {
                "title": norm(submission.title),
                "score": int(submission.score),
                "upvote_ratio": submission.upvote_ratio,
                "url": submission.url,
                "author": test_redditor(submission),
                "num_comments": int(submission.num_comments),
                "selftext": norm(submission.selftext),
                "comments": {}
            }
            for comment in submission.comments.list():
                comment_data[submission.id]['comments'][comment.id] = {}
                c_entry = comment_data[submission.id]['comments'][comment.id]
                c_entry['num_reports'] = comment.num_reports
                c_entry['score'] = int(comment.score)
                c_entry['body'] = norm(comment.body)
                c_entry['ups'] = int(comment.ups)
                c_entry['downs'] = int(comment.downs)
                c_entry['depth'] = int(comment.depth)

        # Write data to file, if Watson query fails file will still contain reddit data
        with open(args.o, "w") as f:
            f.write(json.dumps(comment_data))

        # Add Watson NLU results
        nlucalls = 0
        for s_id in comment_data:
            aggregate = ''
            #comment_data[s_id]['nlu'] = nlu.analyze(
            #    text=comment_data[s_id]['selftext'],
            #    features=[features.Entities(), features.Keywords()],
            #    language='en')
            nlucalls += 1
            aggregate += comment_data[s_id]['selftext']
            for c_id in comment_data[s_id]['comments']:
                c = comment_data[s_id]['comments'][c_id]
                #print c['body']
                #c['nlu'] = nlu.analyze(
                #    text=c['body'],
                #    features=[features.Entities(), features.Keywords()],
                #    language='en')
                nlucalls += 1
                aggregate += c['body']
            #comment_data[s_id]['agg_nlu'] = nlu.analyze(
            #    text=aggregate,
            #    features=[features.Entities(), features.Keywords()],
            #    language='en')
            nlucalls += 1

        print "Program made %s calls to Watson" % nlucalls
        exit()
        # Write complete dataset to file
        with open(args.o, "w") as f:
            f.write(json.dumps(comment_data))
        import ipdb
        ipdb.set_trace()

    else:
        try:
            # Open existing data file
            f = open(args.o, "rw")
            comment_data = json.loads(f.read())
            # Do something with data
        except IOError as oops:
            print oops


if __name__ == "__main__":
    main()
