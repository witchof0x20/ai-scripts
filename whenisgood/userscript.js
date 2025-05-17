// ==UserScript==
// @name         Copy Respondents JSON (Bottom Button)
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Adds a button at the bottom-right corner to copy the respondents JSON to the clipboard
// @author       Jade Harley
// @match        https://whenisgood.net/*/results/*
// @grant        GM_setClipboard
// ==/UserScript==

(function() {
    'use strict';

    function copyRespondentsToClipboard() {
        if (typeof respondents !== 'undefined') {
            const jsonString = JSON.stringify(Object.assign({}, respondents), null, 2);
            GM_setClipboard(jsonString);
            alert("Respondents JSON copied to clipboard!");
        } else {
            alert("Error: respondents object is undefined!");
        }
    }

    function addCopyButton() {
        const button = document.createElement("button");
        button.innerText = "Copy Respondents JSON";
        button.style.position = "fixed";
        button.style.bottom = "10px";  // Placed at the bottom
        button.style.right = "10px";   // Placed at the right
        button.style.zIndex = "10000";
        button.style.padding = "10px 15px";
        button.style.background = "#007BFF";
        button.style.color = "white";
        button.style.border = "none";
        button.style.borderRadius = "5px";
        button.style.cursor = "pointer";
        button.style.boxShadow = "0px 4px 6px rgba(0, 0, 0, 0.1)";

        button.addEventListener("click", copyRespondentsToClipboard);

        document.body.appendChild(button);
    }

    window.addEventListener("load", addCopyButton);
})();
