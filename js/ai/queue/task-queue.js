class TaskQueue {
constructor(concurrency) {
this.concurrency=concurrency;
this.queue=[];
this.activeCount=0;
}

add(task) {
return new Promise((resolve,reject)=>{
this.queue.push(()=>task().then(resolve).catch(reject));
this.processQueue();
});
}

async processQueue() {
if (this.activeCount>=this.concurrency||this.queue.length===0) {
return;
}

const task=this.queue.shift();
this.activeCount++;

try {
console.log("task is run.");
await task();
} catch (error) {
console.error("Task error:",error);
} finally {
this.activeCount--;
this.processQueue();
}
}

getActiveCount() {
return this.activeCount;
}

getWaitingCount() {
return this.queue.length;
}

getTotalCount() {
return this.activeCount+this.queue.length;
}

getStatus() {
return {
active: this.getActiveCount(),
waiting: this.getWaitingCount(),
total: this.getTotalCount()
};
}
}
