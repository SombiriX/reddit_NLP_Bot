'''
This program pulls comments from reddit for further analysis using natural language processing
Author Sombiri Enwemeka
'''
import sys
import os
import praw
import json
import argparse
import time
from unicodedata import normalize
from operator import itemgetter
from google.cloud.gapic.language.v1beta2 import enums
from google.cloud.gapic.language.v1beta2 import language_service_client
from google.cloud.proto.language.v1beta2 import language_service_pb2
from google.gax import errors

sys.path.append(os.path.join(os.getcwd(), '..'))


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


def get_entity_sentiment(text):
    '''
    Detects entity sentiment in the provided text.
    '''
    language_client = language_service_client.LanguageServiceClient()
    document = language_service_pb2.Document()

    #if isinstance(text, six.binary_type):
    #    text = text.decode('utf-8')

    document.content = text.encode('utf-8')
    document.type = enums.Document.Type.PLAIN_TEXT

    encoding = enums.EncodingType.UTF32
    if sys.maxunicode == 65535:
        encoding = enums.EncodingType.UTF16

    result = language_client.analyze_entity_sentiment(document, encoding)

    e_list = []
    for entity in result.entities:
        if abs(entity.sentiment.magnitude - 0.0) > 0.001:
            e_list.append({
                "type": entity.type,
                "name": entity.name,
                "salience": entity.salience,
                "sent_score": entity.sentiment.score,
                "sent_mag": entity.sentiment.magnitude})
    return sorted(e_list, key=itemgetter('salience'), reverse=True)


def update_reddit_comments(args):
    api_keys = None
    try:
        with open(args.k, 'r') as fp:
            api_keys = json.load(fp)
    except IOError as oops:
        print "Error loading Reddit Authentication\r\n%s" % oops
        exit()

    # Get all comment text from top n subreddit posts
    reddit = praw.Reddit(
        client_id=api_keys['reddit'][0],
        client_secret=api_keys['reddit'][1],
        user_agent=api_keys['reddit'][2])
    subreddit = reddit.subreddit(args.subreddit)

    comment_data = {}
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

    # Write comment data to file
    comment_data['num_posts'] = args.n
    with open(args.o, "w") as f:
        f.write(json.dumps(comment_data))
    return comment_data


def main():
    '''
    Main script execution
    '''

    parser = argparse.ArgumentParser(description='Analyze reddit comments')
    #parser.add_argument('-r', action='store_true', help='refresh site data')
    parser.add_argument('--subreddit', default='the_donald', help='Subreddit to examine')
    parser.add_argument('-n', default=5, help='Number of posts to examine')
    parser.add_argument('-o', default='../commentData.json', help='Output file name')
    parser.add_argument('-k', default='../apiKeys.json', help='Path to API keys file')
    args = parser.parse_args()

    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '../redditNLP.json'

    # Check whether to update comment data
    comment_data = {}
    if os.path.isfile(args.o):
        f = open(args.o, "r")
        comment_data = json.loads(f.read())
        if not comment_data['num_posts'] is args.n:
            del(comment_data)
            comment_data = update_reddit_comments(args)
        f.close()
    else:
        comment_data = update_reddit_comments(args)

    # Add natural laguage processing results
    nlp_calls = 0
    for s_id in comment_data:
        # Skip validation entry
        if s_id == "num_posts":
            break
        # Try each request until it works
        while True:
            try:
                aggregate = ''
                nlp_calls += 1
                x = time.time()
                comment_data[s_id]['entities'] = get_entity_sentiment(comment_data[s_id]['selftext'])
                print "Called NLP Service. %s total calls. Call took %ss." % (nlp_calls, time.time()-x)

                aggregate += comment_data[s_id]['selftext']

                for c_id in comment_data[s_id]['comments']:
                    c = comment_data[s_id]['comments'][c_id]
                    nlp_calls += 1
                    x = time.time()
                    c['entities'] = get_entity_sentiment(comment_data[s_id]['selftext'])
                    print "Called NLP Service. %s total calls. Call took %ss." % (nlp_calls, time.time()-x)

                    aggregate += c['body']

                comment_data[s_id]['agg_entities'] = get_entity_sentiment(aggregate)
                nlp_calls += 1
                print "Called NLP Service. %s total calls." % nlp_calls
            except errors.RetryError as te:
                print "Network is acting up again, let's give it a sec: %s" % te
                time.sleep(30)
                continue
            break

    print "Program made %s NLP calls" % nlp_calls
    del os.environ['GOOGLE_APPLICATION_CREDENTIALS']

    # Write complete dataset to file
    with open(args.o, "w") as f:
        f.write(json.dumps(comment_data))
    exit()


if __name__ == "__main__":
    main()
