// Title case for English titles, by the English rules of the wiki page
// Title Capitalization: each word starts with a capital, except inside the
// title the articles, the coordinating conjunctions, "to" and the
// prepositions of fewer than five letters below. A word with a capital
// after its first letter, such as USA, X-Men or McCoy, stays as it is; a
// title entered in capitals only is put in lower case first.
function toTitleCase(title) {
    const prepositions = ['amid', 'as', 'at', 'atop', 'by', 'down', 'for',
                          'from', 'in', 'into', 'like', 'near', 'of', 'off',
                          'on', 'onto', 'out', 'over', 'past', 'per',
                          'till', 'to', 'unto', 'up', 'upon', 'via', 'vs',
                          'with'];
    const smallWords = prepositions.concat(['a', 'an', 'and', 'but', 'nor',
                                            'or', 'the']);
    const bare = word => word.replace(/\P{L}/gu, '').toLowerCase();
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
        if (/\p{L}.*\p{Lu}/u.test(word)) {
            return word;
        }
        // a preposition is followed by its object: one of the list before a
        // comma, as in Go Down, Moses, or before another preposition, as in
        // Time Out of Mind, gets a capital
        const next = /[,;:!?]$/.test(word) ? null :
            title.slice(offset + word.length).match(/^(?:\s+|-)([^\s-]+)/);
        const object = next && !prepositions.includes(bare(next[1]));
        if (inside && smallWords.includes(bare(word)) &&
                (object || !prepositions.includes(bare(word)))) {
            return word.toLowerCase();
        }
        // a word that starts with a digit, such as 2nd, stays as it is
        return word.replace(/^[^\p{L}\p{N}]*\p{L}/u,
                            start => start.toUpperCase());
    });
}
