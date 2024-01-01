const appendElements = async (scrollElement, counter, baseUrl, addUrl) => {
  let url = `${baseUrl}${addUrl}${counter + 1}`

  let req = await fetch(url);

  if (req.ok) {
    let body = await req.text();
    scrollElement.innerHTML += body;
  } else {
    end = true;
  }
}

const attachInfiniteScroll = (sentinel, scrollElement, baseUrl, addUrl, direction) => {
  let counter = 1;
  let end = false;

  let observer = new IntersectionObserver(async (entries) => {
    let bottomEntry = entries[0];

    if (!end && bottomEntry.intersectionRatio > 0) {
      if (direction < 0){
        var url = `${baseUrl}${addUrl}-${counter + 1}`;
      } else {
        var url = `${baseUrl}${addUrl}${counter + 1}`;
      }
      let req = await fetch(url);

      if (req.ok) {
        let body = await req.text();
        if (direction < 0){
          scrollElement.innerHTML = body + scrollElement.innerHTML;
          let elements = document.getElementById('top-scroll-element').getElementsByTagName('p');
          window.scrollTo(0, elements[1].offsetTop);
        } else {
          scrollElement.innerHTML += body ;
        }
        counter += 1;
      } else {
        end = true;
      }
    }
  })
  observer.observe(sentinel);
};

