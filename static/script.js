document.getElementById("leaveForm").onsubmit = function(e){
    e.preventDefault();

    let formData = new FormData(this);

    fetch("/apply", {
        method: "POST",
        body: formData
    }).then(res => res.json())
    .then(data => {
        document.getElementById("result").innerText = data.message;
    });
};
