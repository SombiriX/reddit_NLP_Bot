'''
This program pulls comments from reddit for further analysis using natural
language processing
Author Sombiri Enwemeka
'''
import sys
import os
import praw
import json
import argparse
import time
from datetime import timedelta
from unicodedata import normalize
from operator import itemgetter
from google.cloud.gapic.language.v1beta2 import enums
from google.cloud.gapic.language.v1beta2 import language_service_client
from google.cloud.proto.language.v1beta2 import language_service_pb2
from google.gax import errors

sys.path.append(os.path.join(os.getcwd(), '..'))


def norm(text):
    '''
    Cleans up encoding for input text
    Input: Text to normalize
    Return: Normalized text
    '''
    if text is None:
        return None
    return normalize('NFKD', text).encode('ascii', 'ignore')


def test_redditor(submission):
    '''
    Make sure the intended value exists
    Input: PRAW submission object
    Return: Normalized submission author name
    '''
    if submission is None:
        return None
    if submission.author is None:
        return None
    return norm(submission.author.name)


def get_entity_sentiment(text):
    '''
    Detects entities and sentiment about them from the provided text.
    Input: Body of text to analyze
    Return: List of entities sorted on salience (relevance to text body)
    '''
    language_client = language_service_client.LanguageServiceClient()
    document = language_service_pb2.Document()

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


def get_reddit_comments(args):
    '''
    Uses PRAW to access reddit and download comments and associated data
    checks if comment file already exist or the requested number of submissions
    has been updated to prevent unnecessary queries.
    Input: Argparse args this program was called with
    Return: Comment data dictionary
    Note: This function writes the downloaded comments to a JSON file
    '''
    # Check whether to update comment data
    subm_data = []
    num_entries = 0
    if os.path.isfile(args.o):
        f = open(args.o, "r")
        subm_data = json.loads(f.read())
        if subm_data[-1] is args.n and isinstance(subm_data[-2], int):
            f.close()
            return subm_data

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

    # Put the reddit data into a dictionary
    for submission in subreddit.top(time_filter='all', limit=args.n):
        submission.comments.replace_more(limit=0)
        sub_comments = []
        num_entries += 1
        aggregate = ''
        for comment in submission.comments.list():
            c_entry = {
                "num_reports": comment.num_reports,
                "score": int(comment.score),
                "body": norm(comment.body),
                "ups": int(comment.ups),
                "downs": int(comment.downs),
                "depth": int(comment.depth)
            }
            aggregate += c_entry['body'] + '\r\n'
            sub_comments.append(c_entry)
            num_entries += 1

        subm_data.append({
            "title": norm(submission.title),
            "score": int(submission.score),
            "upvote_ratio": submission.upvote_ratio,
            "url": submission.url,
            "author": test_redditor(submission),
            "num_comments": int(submission.num_comments),
            "selftext": norm(submission.selftext),
            "comments": sub_comments,
            "aggregate": norm(submission.title)
            + '\r\n' + norm(submission.selftext)
            + '\r\n' + aggregate
        })
    # Write comment data to file
    subm_data.append(num_entries)
    subm_data.append(args.n)
    with open(args.o, "w") as f:
        f.write(json.dumps(subm_data))
    return subm_data


def main():
    '''
    Main script execution
    '''

    parser = argparse.ArgumentParser(description='Analyze reddit comments')
    parser.add_argument(
        '--subreddit',
        default='the_donald',
        help='Subreddit to examine')
    parser.add_argument(
        '-n',
        default=10,
        help='Number of posts to examine')
    parser.add_argument(
        '-o',
        default='../commentData.json',
        help='Output file name')
    parser.add_argument(
        '-k',
        default='../apiKeys.json',
        help='Path to API keys file')
    args = parser.parse_args()

    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '../redditNLP.json'
    start_time = time.time()

    subm_data = get_reddit_comments(args)

    # Add natural language processing results
    nlp_calls = 0
    outages = 0
    for subm in subm_data:
        while True:
            try:
                # Skip validation entry
                if isinstance(subm, int):
                    break

                x = time.time()
                subm['ents_self'] = get_entity_sentiment(subm['selftext'])
                nlp_calls += 1
                print "Called NLP Service. %s total calls. " \
                    "Call took %0.3fs." % (nlp_calls, time.time()-x)
                subm['ents_agg'] = get_entity_sentiment(subm['aggregate'])
                nlp_calls += 1
                print "Called NLP Service. %s total calls. " \
                    "Call took %0.3fs." % (nlp_calls, time.time()-x)
            except errors.RetryError:
                outages += 1
                nlp_calls -= 1
                print "The network is acting up again, let's give it a moment"
                print "%s outages so far." % outages
                time.sleep(30)
                continue
            break

    # Write complete dataset to file
    with open(args.o, "w") as f:
        f.write(json.dumps(subm_data))

    # Output some run information
    print "Made %s NLP calls " % nlp_calls
    print "Runtime: %s" % str(timedelta(seconds=time.time()-start_time))
    print "There were %s network outages during this run" % outages
    del os.environ['GOOGLE_APPLICATION_CREDENTIALS']
    exit()


if __name__ == "__main__":
    main()
