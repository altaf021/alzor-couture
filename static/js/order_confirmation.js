(function () {

    "use strict";


    const printButton =
        document.getElementById(
            "printOrderButton"
        );


    if (!printButton) {
        return;
    }


    printButton.addEventListener(
        "click",
        function () {

            window.print();

        }
    );

})();