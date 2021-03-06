#!/usr/bin/env python3
"""
data formats

PROFESSOR[prof_id]["salary"][year][deltatype][salarytype] == salary
PROFESSOR[prof_id][aggregator][year][centrality_measure] == aggregator(centrality_measure) for prof_id in year
PROFESSOR = {
	"P_MUKHERJEE": {
		"salary": {
			2004: {
				"": {"gross", "base", "overtime", "extra"},
				"Δ": {"gross", "base", "overtime", "extra"},
				"p": {"gross", "base", "overtime", "extra"},
			}
		},
		"centrality": {
			2004: {"pagerank", "citations", "Δpagerank", "Δcitations"}
		},
		"phd_year": 1970,
		"papers": set(["hep-th/049382", "1183.2066"])
	}
}

CENTRALITY[paperid][year][centrality_measure] == centrality
CENTRALITY = {
	"hep-th/04392": {
		2004: { "pagerank":1, "citations":2, "Δpagerank":0.5, "Δcitations":2 },
		...
		2011: { "pagerank":1, "citations":2, "Δpagerank":0.5, "Δcitations":2 }
	},
}
"""
import os
import csv
import itertools as I
from collections import namedtuple
from collections import Counter
from collections import defaultdict
infinite_dict = lambda: defaultdict(infinite_dict)
call = lambda f: f()


# File paths
ABSPATH = os.path.dirname(__file__)
CENTRALITY_DIR = os.path.join(ABSPATH, 'raw', 'centrality')
SALARY_FILE = os.path.join(ABSPATH, 'raw', 'salary', 'hep-th_2004_2010.csv')
PAPER_FILE = os.path.join(ABSPATH, 'raw', 'paper', 'hep-th_ucprofpapers_2004_2010.csv')
OUTPUT_DIR = os.path.join(ABSPATH, 'output')
PHD_FILE = os.path.join(ABSPATH, 'raw', 'prof', 'hep-th_phdyear_2004_2010.csv')


YEARS = range(2004, 2011)
CENTRALITY = infinite_dict()
PROFESSOR = infinite_dict()


def calc_prof_aggregation(aggregator):
	'''Calculates the aggregate score, using the given aggregate index, for every (professor, year, centrality measure), and stores the result in prof[aggregator].'''
	print('\t{0}'.format(aggregator.__name__))
	for author_key, prof in PROFESSOR.items():
		for year in YEARS:
			for cm in CENTRALITY_MEASURES:
				prof[aggregator][year][cm] = aggregator(prof["papers"], lambda paper: CENTRALITY[paper][year][cm] or 0)	# @@@@@ Taking an absent centrality as 0.

@call
def AGGREGATORS():
	def Σ(profpapers, paper_centralities):
		return sum((paper_centralities(paper) for paper in profpapers))
	
	def h(profpapers, paper_centralities):
		# c → number of papers with centrality c
		centrality_counts = Counter()
		for paper in profpapers:
			centrality_counts[paper_centralities(paper)] += 1
		h = 0
		while sum((cnt for centrality, cnt in centrality_counts.items() if centrality >= h)) >= h:
			# at least h papers have centrality at least h
			h += 1
		# h is the smallest integer s.t. fewer than h papers have centrality at least h
		return h - 1
		
	def g(profpapers, paper_centralities):
		# n → total centrality of top n papers
		cum_centrality = list(I.accumulate(I.chain([0], reversed(sorted(map(paper_centralities, profpapers))))))
		g = 0
		try:
			while cum_centrality[g] >= g * g:
				g += 1
		except IndexError: pass	# if every paper is significant
		return g - 1
	
	return locals().values()

CENTRALITY_MEASURES = ('pagerank', 'citations', 'Δpagerank', 'Δcitations',)


def load_centrality():
	'''Loads and normalizes the input centralities and calculates the changes.'''
	# parse and load
	for filename in os.listdir(CENTRALITY_DIR):
		field, year, etc = filename.split("_")
		year = int(year)
		with open(os.path.join(CENTRALITY_DIR, filename), 'rt') as f:
			f.readline()
			for line in f.readlines():
				paper = line.split(",")
				id = paper[0]
				citations = int(paper[2])
				pagerank = float(paper[5])
				CENTRALITY[id][year] = {"pagerank":pagerank, "citations":citations}
	# calculate delta centrality
	for paperid in CENTRALITY:
		for year in YEARS:
			curr = CENTRALITY[paperid][year]
			prev = CENTRALITY[paperid][year - 1]
			curr["Δpagerank"] = (curr["pagerank"] or 0) - (prev["pagerank"] or 0)
			curr["Δcitations"] = (curr["citations"] or 0) - (prev["citations"] or 0)
	# @@@@@ It seems some papers don't have centralities!


def load_salary():
	'''Loads and normalizes the input salaries and calculates the changes.'''
	SALARY_TYPES = ("gross", "base", "overtime", "extra")
	# parse and load
	with open(SALARY_FILE, "rt", newline="") as f:
		for info in map(namedtuple("SalaryInfo", ['author_key', 'year', 'gross', 'base', 'overtime', 'extra', 'x0', 'x1', 'x2', 'x3'])._make, csv.reader(f)):
			PROFESSOR[info.author_key]["salary"][int(info.year)] = {
				"": {
					"gross": float(info.gross),
					"base": float(info.base),
					"overtime": float(info.overtime),
					"extra": float(info.extra),
				},
				"Δ": defaultdict(lambda: defaultdict(lambda: None)),
				"p": defaultdict(lambda: defaultdict(lambda: None)),
			}
	for author_key, prof in PROFESSOR.items():
		salary = prof["salary"]
		for year in YEARS:
			if year in salary and year-1 in salary:
				curr = salary[year]
				prev = salary[year-1]
				for t in SALARY_TYPES:
					curr["Δ"][t] = curr[""][t] - prev[""][t]
					curr["p"][t] = curr["Δ"][t] / prev[""][t] if prev[""][t] else None	# divide-by-0 case


def load_prof_paper():
	with open(PAPER_FILE) as f:
		for line in f.readlines():
			line = line.strip()
			author_key, arxiv_ids = line.split(",")
			arxiv_ids = arxiv_ids.split("|")
			if author_key not in PROFESSOR:
				PROFESSOR[author_key] = {}
			prof = PROFESSOR[author_key]
			prof["papers"] = set(arxiv_ids)


def load_prof_phd_year():
	with open(PHD_FILE) as f:
		f.readline()
		for line in f.readlines():
			line = line.strip()
			author_key, year = line.split(",")
			year = int(year)
			if author_key not in PROFESSOR:
				PROFESSOR[author_key] = {}
			PROFESSOR[author_key]["phd_year"] = year


def export_diff(outfolder):
	if not os.path.exists(outfolder):
		os.makedirs(outfolder)
	with open(os.path.join(outfolder, "diff_allyears.csv"), "w", newline="") as f:
		fieldnames = list(I.chain(('year','author_id','years_since_phd','gross','base','Δgross','Δbase','pgross','pbase',),
			["{0}({1})".format(agg.__name__, c) for c in CENTRALITY_MEASURES for agg in AGGREGATORS]))
		f = csv.DictWriter(f, fieldnames)
		f.writeheader()
		for author_id, prof in PROFESSOR.items():
			for year in YEARS:
				salary = prof["salary"][year]
				if salary["Δ"]["gross"] and 'phd_year' in prof:
					d = {
						'year': year,
						'author_id': author_id,
						'years_since_phd': year - prof['phd_year'],
					}
					# selected salary measures
					d.update({"{0}{1}".format(deltatype, salarytype): salary[deltatype][salarytype]
						for deltatype in ('', 'Δ', 'p',) for salarytype in ('gross', 'base',)})
					# all the possible (aggregator, centrality) combinations
					d.update({"{0}({1})".format(agg.__name__, c): prof[agg][year][c]
						for c in CENTRALITY_MEASURES for agg in AGGREGATORS})
					
					f.writerow(d)


def load_and_process():
	print('loading salary...')
	load_salary()
	print('loading uc prof papers and phd year...')
	load_prof_paper()
	load_prof_phd_year()
	print('loading centrality for papers...')
	load_centrality()
	print('aggregating prof centralities...')
	for agg in AGGREGATORS:
		calc_prof_aggregation(agg)


if __name__ == "__main__":
	load_and_process()
	print('exporting...')
	export_diff(OUTPUT_DIR)
	print('Done')