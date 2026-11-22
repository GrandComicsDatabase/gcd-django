// Title case for English titles, by the English rules of the wiki page
// Title Capitalization: each word starts with a capital, except inside the
// title the articles, the coordinating conjunctions, "to" and the
// prepositions of fewer than five letters below. A word with a capital
// after its first letter, such as USA, X-Men or McCoy, stays as it is; a
// title entered in capitals only is put in lower case first.
function toTitleCase(title) {
    const smallWords = ['a', 'an', 'and', 'as', 'at', 'but', 'by', 'for',
                        'from', 'in', 'into', 'nor', 'of', 'on', 'onto',
                        'or', 'per', 'the', 'to', 'upon', 'via', 'vs',
                        'with'];
    if (title === title.toUpperCase()) {
        title = title.toLowerCase();
    }
    const end = title.trimEnd().length;
    // words are separated by spaces and hyphens, as in Spider-Man
    return title.replace(/[^\s-]+/g, function (word, offset) {
        const before = title.slice(0, offset).trim();
        // a colon, ! or ? and a dash between spaces start a new part
        const inside = before && !/[:!?]$|\s-+$/.test(before) &&
                       offset + word.length < end;
        const bare = word.replace(/\P{L}/gu, '').toLowerCase();
        if (/\p{L}.*\p{Lu}/u.test(word)) {
            return word;
        }
        if (inside && smallWords.includes(bare)) {
            return word.toLowerCase();
        }
        // a word that starts with a digit, such as 2nd, stays as it is
        return word.replace(/^[^\p{L}\p{N}]*\p{L}/u,
                            start => start.toUpperCase());
    });
}
