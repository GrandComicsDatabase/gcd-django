  function initializeSortableReorder(tbody, sort_field, options = {}) {
    const defaultOptions = {
      animation: 150,
      handle: 'tr',
      ghostClass: 'bg-blue-200',
      multiDrag: true,
      selectedClass: 'bg-blue-100',
      onEnd: function() {
        const inputs = tbody.querySelectorAll(`.${sort_field}`);
        inputs.forEach((input, index) => {
          input.value = (index + 1);
        });
      }
    };
    
    Sortable.create(tbody, { ...defaultOptions, ...options });
  }
