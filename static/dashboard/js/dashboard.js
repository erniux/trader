function paginateBalances(page = 1) {
    const rows = document.querySelectorAll('#balances-table tbody tr');
    const pagination = document.getElementById('pagination');
    const totalRows = rows.length;
    const rowsPerPage = 5; // Elementos por página
    const totalPages = Math.ceil(totalRows / rowsPerPage);

    currentPage = page;

    // Mostrar solo las filas de la página actual
    rows.forEach((row, index) => {
        row.style.display = (index >= (currentPage - 1) * rowsPerPage && index < currentPage * rowsPerPage) ? '' : 'none';
    });

    // Generar botones de paginación
    pagination.innerHTML = '';
    for (let i = 1; i <= totalPages; i++) {
        const li = document.createElement('li');
        li.className = `page-item ${i === currentPage ? 'active' : ''}`;
        li.innerHTML = `<a class="page-link" href="#">${i}</a>`;
        li.addEventListener('click', () => paginateBalances(i));
        pagination.appendChild(li);
    }
}

function filterBalances(query = '') {
    const rows = document.querySelectorAll('#balances-table tbody tr');
    rows.forEach(row => {
        const asset = row.children[0].textContent.toLowerCase();
        row.style.display = asset.includes(query) ? '' : 'none';
    });
}

function fetchBalances() {
    fetch('/api/balances/')
        .then(response => response.json())
        .then(data => {
            const tableBody = document.querySelector('#balances-table tbody');
            const currentQuery = document.getElementById('search-bar').value.toLowerCase(); // Conserva la búsqueda actual
            const currentPage = parseInt(document.querySelector('.page-item.active a')?.textContent || 1); // Página actual

            tableBody.innerHTML = ''; // Limpia las filas actuales

            // Agregar nuevas filas
            data.balances.forEach(balance => {
                const row = `
                    <tr>
                        <td>${balance.asset}</td>
                        <td>${balance.free.toFixed(8)}</td>
                        <td>${balance.locked.toFixed(8)}</td>
                    </tr>`;
                tableBody.insertAdjacentHTML('beforeend', row);
            });

            // Reaplica el filtro y la paginación
            filterBalances(currentQuery);
            paginateBalances(currentPage);
        })
        .catch(error => console.error('Error fetching balances:', error));
}

// Actualizar balances automáticamente cada 5 minutos (300000 ms)
setInterval(fetchBalances, 300000);

// Llamar manualmente la primera vez para inicializar la tabla
fetchBalances();