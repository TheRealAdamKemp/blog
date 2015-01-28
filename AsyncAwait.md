<!-- !b
kind: post
service: blogger
title: Best Post Ever
labels: mobile
draft: True
-->

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Aliquam nibh nunc, egestas quis enim mattis, ultrices dignissim erat. Etiam ac laoreet erat, tincidunt rhoncus nulla. Sed accumsan quam non dolor euismod fermentum. Sed non eros consectetur, aliquet massa ut, pellentesque mauris. Suspendisse id purus in ex mollis vestibulum sed sed eros. Phasellus dictum vel ante quis vehicula. Sed non metus lacus. Nunc mattis turpis tortor, vel gravida dui rhoncus ultricies. Maecenas aliquet libero vestibulum leo efficitur elementum. Nam aliquet pretium nisi, eget congue nisi sagittis et. Morbi cursus venenatis metus vitae scelerisque.

<!--more-->

[TOC]

There probably still is a simpler way, but you have to understand what async/await actually does. It doesn't make a method run in the background. It takes a method that has to wait on something in the background and it makes that code simpler. For example, usually if you call some method that runs asynchronously and you need to get a response then you pass in a callback. It might look like this:

    private void DoSomethingAsync()
    {
        DoSomethingElseAsync(result =>
        {
            // Use result
        });
    }

But then you also need to handle errors so it might look like this:

    private void DoSomethingAsync()
    {
        DoSomethingElseAsync((result, error) =>
        {
            if (error == null)
            {
                // Use result
            }
            else
            {
                // Report error
            }
        });
    }

And then you might need to chain more async methods so it starts looking like this mess:

    private void DoSomethingAsync()
    {
        DoSomethingElseAsync((result, error) =>
        {
            if (error == null)
            {
                DoThirdThingAsync(result, (result2, error2) =>
                {
                    if (error == null)
                    {
                        // Use result2
                    }
                    else
                    {
                        // Report error2
                    }
            }
            else
            {
                // Report error
            }
        });
    }

Oh, and maybe the callbacks are on the wrong thread so you have to do stuff like this:

    private void DoSomethingAsync()
    {
        DoSomethingElseAsync((result, error) =>
        {
            if (error == null)
            {
                DoThirdThingAsync(result, (result2, error2) =>
                {
                    if (error == null)
                    {
                        BeginInvokeOnMainThread(() =>
                        {
                            // Use result2
                        });
                    }
                    else
                    {
                        BeginInvokeOnMainThread(() =>
                        {
                            // Report error2
                        });
                    }
            }
            else
            {
                BeginInvokeOnMainThread(() =>
                {
                    // Report error
                });
            }
        });
    }

Whew! That's complicated, ugly, and very error-prone.

It is assumed in these examples that `DoSomethingElseAsync` and `DoThirdThingAsync` already have some mechanism for starting a background task (maybe using `Task.StartNew`). The async/await feature doesn't help with that. But what it does help with is cleaning up this mess of nested callbacks and ugly error handling. With async/await you can write the above example like this:

    private void DoSomethingAsync()
    {
        try
        {
            var finalResult = await DoThirdThingAsync(await DoSomethingElseAsync());
        }
        catch (Exception e)
        {
            // Report error
        }
    }

Now you don't have any ugly callbacks that obfuscate the order in which things happen, and your error handling is shared in one normal-looking try/catch.  The compiler takes care of turning this code into something equivalent to the above code, but your code stays simple and understandable. It also takes care of switching back to the right thread after the async methods return (either an error or a successful completion) so you don't have to worry about using `BeginInvokeOnMainThread`. That's what async/await does. You can read more here: http://msdn.microsoft.com/en-us/library/hh191443.aspx
